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
        
        # Try to keep context lightweight to avoid PII; include kind/key only
        try:
            # Context API: pull "kind" and "key" safely
            if context.multiple:
                kinds = sorted([k for k in context.kinds()])
                ctx_repr = {"kinds": kinds}
            else:
                kinds = [context.kind]
                ctx_repr = {"kinds": kinds}

            # Try to include a stable key if present (avoid dumping all attributes)
            if not context.multiple and context.key is not None:
                ctx_repr["key"] = context.key
        except Exception:
            ctx_repr = {"repr": str(context)}

        payload = {
            "event": "before_flag_evaluation",
            "flagKey": flag_key,
            "defaultValue": default_value,
            "context": ctx_repr,
        }
        json_log(payload)
        
        return data  # Return the data dict as required

    # Signature per LD Python SDK v9+
    def after_evaluation(self, series_context, data, detail):
        # Extract context and flag key from series_context
        context = series_context.context
        flag_key = series_context.key
        
        # Try to keep context lightweight to avoid PII; include kind/key only
        try:
            # Context API: pull "kind" and "key" safely
            if context.multiple:
                kinds = sorted([k for k in context.kinds()])
                ctx_repr = {"kinds": kinds}
            else:
                kinds = [context.kind]
                ctx_repr = {"kinds": kinds}

            # Try to include a stable key if present (avoid dumping all attributes)
            # NOTE: For multi-kind, there may be multiple keys; keep it minimal.
            if not context.multiple and context.key is not None:
                ctx_repr["key"] = context.key
        except Exception:
            ctx_repr = {"repr": str(context)}

        reason = getattr(detail, "reason", None)
        reason_kind = getattr(reason, "kind", None)
        reason_dict = {"kind": reason_kind} if reason_kind else None

        payload = {
            "event": "after_flag_evaluation",
            "flagKey": flag_key,
            "value": getattr(detail, "value", None),
            "variationIndex": getattr(detail, "variation_index", None),
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
    args = parser.parse_args()

    default_value = True if args.default.lower() == "true" else False

    # ---- LD client config (streaming on; events enabled by default)
    config = Config(sdk_key=args.sdk_key, stream=True, offline=False, hooks=[EvaluationLoggingHook()])
    client = LDClient(config)

    try:
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
