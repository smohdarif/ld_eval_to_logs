#!/usr/bin/env python3
import argparse
import json
import logging
import sys
import time

from ldclient import LDClient, Config, Context   # ✅ proper LD imports
from ldclient.hook import Hook, Metadata        # ✅ hooks API (Python SDK v9+)


# ---- JSON logger to stdout (Dynatrace picks this up via OneAgent/Operator)
logger = logging.getLogger("ld-json")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(message)s"))  # emit raw JSON lines
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def json_log(payload: dict):
    payload.setdefault("timestamp", int(time.time() * 1000))
    payload.setdefault("source", "LaunchDarkly")
    # Don't set default event name - let callers specify it
    logger.info(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


def encode_key(key: str) -> str:
    """
    Encode special characters in context keys to prevent breaking the canonical key format.
    Encodes '%' and ':' characters as they're used as delimiters.
    """
    if '%' in key or ':' in key:
        return key.replace('%', '%25').replace(':', '%3A')
    return key


def get_canonical_key(context) -> str:
    """
    Generate a canonical key for the context (for multi-kind contexts).
    Format: kind:key or kind1:key1:kind2:key2 for multi-contexts
    Special characters in keys are encoded to prevent parsing issues.
    """
    try:
        if context.multiple:
            # Multi-kind context
            parts = []
            for kind in sorted(context.kinds()):
                ctx = context.get(kind)
                if ctx and hasattr(ctx, 'key'):
                    parts.append(f"{kind}:{encode_key(ctx.key)}")
            return ":".join(parts) if parts else encode_key(context.key)
        else:
            # Single context
            encoded_key = encode_key(context.key)
            if context.kind and context.kind != "user":
                return f"{context.kind}:{encoded_key}"
            return encoded_key
    except Exception:
        return str(context)


# ---- Hook that logs after each flag evaluation
class EvaluationLoggingHook(Hook):
    @property
    def metadata(self) -> Metadata:
        return Metadata(name="evaluation-logging-hook")

    def before_evaluation(self, series_context, data):
        # Extract context and flag key from series_context
        context = series_context.context
        flag_key = series_context.key
        default_value = series_context.default_value
        method = series_context.method
        
        # Get canonical context key for tracking
        canonical_key = get_canonical_key(context)
        
        # Try to keep context lightweight to avoid PII; include kind/key only
        try:
            # Context API: pull "kind" and "key" safely
            if context.multiple:
                kinds = sorted([k for k in context.kinds()])
                ctx_repr = {"kinds": kinds, "canonicalKey": canonical_key}
            else:
                kinds = [context.kind]
                ctx_repr = {"kinds": kinds, "canonicalKey": canonical_key}

            # Try to include a stable key if present (avoid dumping all attributes)
            if not context.multiple and context.key is not None:
                ctx_repr["key"] = context.key
        except Exception:
            ctx_repr = {"repr": str(context)}

        payload = {
            "event": "before_flag_evaluation",
            "flagKey": flag_key,
            "defaultValue": default_value,
            "method": method,
            "context": ctx_repr,
        }
        json_log(payload)
        
        return data  # Return the data dict as required

    # Signature per LD Python SDK v9+
    def after_evaluation(self, series_context, data, detail):
        # Extract context and flag key from series_context
        context = series_context.context
        flag_key = series_context.key
        method = series_context.method
        
        # Get canonical context key for tracking
        canonical_key = get_canonical_key(context)
        
        # Try to keep context lightweight to avoid PII; include kind/key only
        try:
            # Context API: pull "kind" and "key" safely
            if context.multiple:
                kinds = sorted([k for k in context.kinds()])
                ctx_repr = {"kinds": kinds, "canonicalKey": canonical_key}
            else:
                kinds = [context.kind]
                ctx_repr = {"kinds": kinds, "canonicalKey": canonical_key}

            # Try to include a stable key if present (avoid dumping all attributes)
            # NOTE: For multi-kind, there may be multiple keys; keep it minimal.
            if not context.multiple and context.key is not None:
                ctx_repr["key"] = context.key
        except Exception:
            ctx_repr = {"repr": str(context)}

        # Extract detailed reason information (matching Dynatrace template format)
        reason = getattr(detail, "reason", None)
        reason_dict = None
        if reason:
            reason_dict = {
                "kind": getattr(reason, "kind", None),
            }
            # Add optional reason fields if present
            if hasattr(reason, "rule_id") and reason.rule_id is not None:
                reason_dict["ruleId"] = reason.rule_id
            if hasattr(reason, "rule_index") and reason.rule_index is not None:
                reason_dict["ruleIndex"] = reason.rule_index
            if hasattr(reason, "in_experiment") and reason.in_experiment is not None:
                reason_dict["inExperiment"] = reason.in_experiment
            if hasattr(reason, "error_kind") and reason.error_kind is not None:
                reason_dict["errorKind"] = reason.error_kind
            if hasattr(reason, "prerequisite_key") and reason.prerequisite_key is not None:
                reason_dict["prerequisiteKey"] = reason.prerequisite_key

        payload = {
            "event": "after_flag_evaluation",
            "flagKey": flag_key,
            "value": getattr(detail, "value", None),
            "variationIndex": getattr(detail, "variation_index", None),
            "defaultValue": series_context.default_value,
            "method": method,
            "reason": reason_dict,
            "context": ctx_repr,
        }
        json_log(payload)
        
        return data  # Return the data dict as required


def main():
    parser = argparse.ArgumentParser(description="Evaluate an LD flag and log to stdout (for Dynatrace).")
    parser.add_argument("--sdk-key", required=True, help="LaunchDarkly server-side SDK key (environment-specific).")
    parser.add_argument("--project", required=True, help="Project name (for tagging logs; not used by SDK).")
    parser.add_argument("--flag-key", required=True, help="Flag key to evaluate.")
    parser.add_argument("--user-key", default="demo-user-1", help="Context key (default: demo-user-1).")
    parser.add_argument("--default", default="false", choices=["true", "false"],
                        help="Default value if flag not found (bool). Default: false.")
    parser.add_argument("--simulate-down", action="store_true",
                        help="Simulate LaunchDarkly being down (uses invalid endpoints for testing).")
    args = parser.parse_args()

    default_value = True if args.default.lower() == "true" else False

    # ---- LD client config (streaming on; events enabled by default)
    if args.simulate_down:
        # Use invalid endpoints to simulate LD being down
        config = Config(
            sdk_key=args.sdk_key,
            stream=True,
            offline=False,
            stream_uri="https://invalid-ld-endpoint.example.com",
            base_uri="https://invalid-ld-endpoint.example.com",
            events_uri="https://invalid-ld-endpoint.example.com",
            hooks=[EvaluationLoggingHook()],
            initial_reconnect_delay=0.1  # Fail fast for testing
        )
        logger.info(json.dumps({
            "source": "LaunchDarkly",
            "event": "simulation_mode",
            "message": "Simulating LaunchDarkly down - using invalid endpoints"
        }, separators=(",", ":")))
    else:
        config = Config(sdk_key=args.sdk_key, stream=True, offline=False, hooks=[EvaluationLoggingHook()])
    
    client = LDClient(config)

    try:
        # ---- Check data source status (connection to LaunchDarkly)
        data_source_status = client.data_source_status_provider.status
        
        status_payload = {
            "source": "LaunchDarkly",
            "event": "data_source_status",
            "state": str(data_source_status.state.name) if hasattr(data_source_status.state, 'name') else str(data_source_status.state),
            "stateSince": int(data_source_status.since * 1000) if data_source_status.since else None,  # Convert to milliseconds
        }
        
        # Include error if present
        if data_source_status.error:
            error_info = data_source_status.error
            status_payload["lastError"] = {
                "kind": str(error_info.kind.name) if hasattr(error_info.kind, 'name') else str(error_info.kind),
                "statusCode": error_info.status_code if hasattr(error_info, 'status_code') else None,
                "time": int(error_info.time * 1000) if hasattr(error_info, 'time') and error_info.time else None,
            }
        
        logger.info(json.dumps(status_payload, separators=(",", ":")))
        
        # ---- Minimal, privacy-safe context; attach project as an attribute
        ctx_builder = Context.builder(args.user_key)  # ✅ best practice: builder API
        ctx_builder.set("project", args.project)      # tag for dashboards/search
        context = ctx_builder.build()

        # ---- Evaluate once (this will trigger the hook and emit a JSON log line)
        value = client.variation(args.flag_key, context, default_value)

        # Also print a small human hint (optional)
        logger.info(json.dumps({
            "source": "LaunchDarkly",
            "event": "evaluation_result_summary",
            "flagKey": args.flag_key,
            "value": value,
            "project": args.project
        }, separators=(",", ":"), ensure_ascii=False))

    finally:
        # Flush any pending events & close cleanly
        client.close()


if __name__ == "__main__":
    main()
