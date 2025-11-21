# LaunchDarkly Evaluation to Logs

A Python script that evaluates LaunchDarkly feature flags and logs the results in JSON format for Dynatrace ingestion.

## Features

- 🎯 Evaluates LaunchDarkly feature flags in real-time
- 📊 Logs before and after evaluation events
- 🔍 JSON output format ready for Dynatrace monitoring
- 🔒 Privacy-safe context handling (minimal PII exposure)
- ⚡ Uses LaunchDarkly Python SDK v9+ hooks API
- 📋 Captures detailed reason fields (ruleId, ruleIndex, inExperiment, errorKind)
- 🔑 Generates canonical keys for single and multi-kind contexts
- 📌 Tracks SDK method invocation (variation, variation_detail, etc.)
- ✅ Aligned with official LaunchDarkly Dynatrace integration template

## Requirements

- Python 3.7+
- LaunchDarkly server-side SDK key
- LaunchDarkly project with feature flags

## Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/ld_eval_to_logs.git
cd ld_eval_to_logs
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

```bash
python3 ld_eval_to_logs.py \
  --sdk-key "YOUR_SDK_KEY" \
  --project "YOUR_PROJECT_NAME" \
  --flag-key "YOUR_FLAG_KEY" \
  --user-key "user-123"
```

### Arguments

- `--sdk-key` (required): LaunchDarkly server-side SDK key
- `--project` (required): Project name for log tagging
- `--flag-key` (required): Feature flag key to evaluate
- `--user-key` (optional): Context key (default: demo-user-1)
- `--default` (optional): Default value if flag not found (true/false, default: false)
- `--simulate-down` (optional): Simulate LaunchDarkly being down for testing failure scenarios

## Example Output

Real output from running the script:

```json
{"event":"before_flag_evaluation","flagKey":"demo-flag","defaultValue":false,"method":"variation","context":{"kinds":["user"],"canonicalKey":"demo-user-1","key":"demo-user-1"},"timestamp":1763670574151,"source":"LaunchDarkly"}
{"event":"after_flag_evaluation","flagKey":"demo-flag","value":true,"variationIndex":0,"defaultValue":false,"method":"variation","reason":{"kind":null},"context":{"kinds":["user"],"canonicalKey":"demo-user-1","key":"demo-user-1"},"timestamp":1763670574151,"source":"LaunchDarkly"}
{"source":"LaunchDarkly","event":"evaluation_result_summary","flagKey":"demo-flag","value":true,"project":"arif-test-project"}
```

### Output Breakdown

**Line 1 - Before Evaluation:**
- Shows the flag about to be evaluated (`demo-flag`)
- Includes the default fallback value (`false`)
- Records the SDK method being called (`variation`)
- Captures context with canonical key for tracking

**Line 2 - After Evaluation:**
- Shows the actual value returned (`true`)
- Variation index `0` indicates which variant was served
- Reason object ready to capture rule matches, experiments, and errors
- Same canonical key for correlation with before event

**Line 3 - Summary:**
- Human-readable summary of the evaluation
- Includes project tag for organizational filtering

### Payload Fields

**Before Evaluation:**
- `event`: Event type (`before_flag_evaluation`)
- `flagKey`: The flag being evaluated
- `defaultValue`: Fallback value if evaluation fails
- `method`: SDK method called (e.g., `variation`, `variation_detail`)
- `context`: User/context information with canonical key
- `timestamp`: Unix timestamp in milliseconds
- `source`: Always "LaunchDarkly"

**After Evaluation:**
- `event`: Event type (`after_flag_evaluation`)
- `flagKey`: The flag that was evaluated
- `value`: Actual value returned by LaunchDarkly
- `variationIndex`: Which variation was served (0, 1, etc.)
- `defaultValue`: The fallback value provided
- `method`: SDK method called
- `reason`: Detailed evaluation reason including:
  - `kind`: Reason type (FALLTHROUGH, RULE_MATCH, TARGET_MATCH, etc.)
  - `ruleId`: ID of the matching rule (if applicable)
  - `ruleIndex`: Index of the matching rule
  - `inExperiment`: Whether this evaluation is part of an experiment
  - `errorKind`: Error type if evaluation failed
  - `prerequisiteKey`: Prerequisite flag that affected this evaluation
- `context`: User/context information with canonical key
- `timestamp`: Unix timestamp in milliseconds

## Hook Execution Flow

When `client.variation()` is called, **both hooks are triggered** in sequence:

```
client.variation() called
    ↓
1. before_evaluation hook executes
   - Logs flag key, context, and default value
   - Executes BEFORE LaunchDarkly evaluates the flag
    ↓
2. SDK evaluates flag
   - Contacts LaunchDarkly to get the flag value
    ↓
3. after_evaluation hook executes
   - Logs the actual result (value, variation index, reason)
   - Executes AFTER LaunchDarkly returns the result
    ↓
client.variation() returns the flag value
```

### Hook Benefits

- **Debugging**: See if the default value is being used vs. actual flag value
- **Latency tracking**: Measure time between before/after timestamps
- **Failure detection**: If after_evaluation never fires, LaunchDarkly might be down
- **Audit trail**: Complete record of what was requested and what was received

### Before vs After

| Hook | Timing | Has Access To |
|------|--------|---------------|
| `before_evaluation` | Before SDK evaluates | flag key, context, default value |
| `after_evaluation` | After SDK evaluates | flag key, context, **actual value**, variation index, reason |

If LaunchDarkly is unreachable, `after_evaluation` will show the default value being used instead of the configured flag value.

## Canonical Context Keys

The script generates canonical keys for tracking contexts consistently:

- **Single user context**: `demo-user-1`
- **Single non-user context**: `organization:org-123`
- **Multi-kind context**: `organization:org-123:user:user-456` (sorted alphabetically)

### Special Character Encoding

Context keys containing special characters are automatically encoded to prevent parsing issues:

- **Colon (`:`)** → `%3A`
- **Percent (`%`)** → `%25`

**Example:**
- Original key: `user:123%test`
- Encoded canonical key: `user%3A123%25test`

This matches the format used by LaunchDarkly's official integrations and allows for:
- Consistent tracking across evaluations
- Easy correlation with LaunchDarkly analytics
- Support for multi-kind contexts in Dynatrace dashboards
- Safe handling of keys with delimiter characters

## References

This implementation is aligned with official LaunchDarkly documentation:

### Python SDK Documentation
- [LDClient.add_hook() API Reference](https://launchdarkly-python-sdk.readthedocs.io/en/latest/api-main.html#ldclient.client.LDClient.add_hook)
- [Hook Class API Reference](https://launchdarkly-python-sdk.readthedocs.io/en/latest/api-main.html#ldclient.hook.Hook)
- [LaunchDarkly Hooks Feature Guide](https://launchdarkly.com/docs/sdk/features/hooks)

### Integration Templates
- [Dynatrace v2 Integration Flag Template](https://github.com/launchdarkly/integration-framework/blob/main/integrations/dynatrace-v2/templates/flag.json.hbs) - Official payload format for Dynatrace integration

## LaunchDarkly Setup

1. Create a project in LaunchDarkly (e.g., `arif-test-project`)
2. Create an environment and get the server-side SDK key
3. Create a boolean feature flag (e.g., `demo-flag`)
4. Turn the flag ON and configure variations

## Testing Failure Scenarios

The `--simulate-down` flag allows you to test how your application behaves when LaunchDarkly is unreachable:

```bash
python3 ld_eval_to_logs.py \
  --sdk-key "YOUR_SDK_KEY" \
  --project "YOUR_PROJECT" \
  --flag-key "YOUR_FLAG" \
  --simulate-down
```

### When LaunchDarkly is Down:

**What happens:**
- SDK cannot connect to LaunchDarkly endpoints
- Default/fallback values are used
- `variationIndex` becomes `null` (key indicator!)
- Hooks still fire and log the evaluation

**Example output:**
```json
{
  "event": "after_flag_evaluation",
  "flagKey": "demo-flag",
  "value": false,             // ← Default value used
  "variationIndex": null,     // ← NULL = LD unreachable!
  "defaultValue": false,
  "method": "variation"
}
```

### Dynatrace Monitoring

Use `variationIndex: null` to create alerts:

```sql
-- Alert when LaunchDarkly is unreachable
SELECT count(*) 
FROM logs 
WHERE variationIndex IS NULL 
AND event = 'after_flag_evaluation'
```

```sql
-- Calculate LaunchDarkly availability
SELECT 
  (COUNT(*) FILTER (WHERE variationIndex IS NOT NULL) * 100.0 / COUNT(*)) as availability_percentage
FROM logs 
WHERE event = 'after_flag_evaluation'
```

## Integration with Dynatrace

The JSON logs are output to stdout and can be ingested by Dynatrace OneAgent or Operator for monitoring and observability.

## License

MIT

