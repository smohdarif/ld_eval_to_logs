# LaunchDarkly Evaluation to Logs

A Python script that evaluates LaunchDarkly feature flags and logs the results in JSON format for Dynatrace ingestion.

## Features

- 🎯 Evaluates LaunchDarkly feature flags in real-time
- 📊 Logs before and after evaluation events
- 🔍 JSON output format ready for Dynatrace monitoring
- 🔒 Privacy-safe context handling (minimal PII exposure)
- ⚡ Uses LaunchDarkly Python SDK v9+ hooks API

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

## Example Output

```json
{"event":"before_flag_evaluation","flagKey":"demo-flag","defaultValue":false,"context":{"kinds":["user"],"key":"demo-user-1"},"timestamp":1763591167760,"source":"LaunchDarkly"}
{"event":"after_flag_evaluation","flagKey":"demo-flag","value":true,"variationIndex":0,"reason":null,"context":{"kinds":["user"],"key":"demo-user-1"},"timestamp":1763591167760,"source":"LaunchDarkly"}
{"source":"LaunchDarkly","event":"evaluation_result_summary","flagKey":"demo-flag","value":true,"project":"arif-test-project"}
```

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

## LaunchDarkly Setup

1. Create a project in LaunchDarkly (e.g., `arif-test-project`)
2. Create an environment and get the server-side SDK key
3. Create a boolean feature flag (e.g., `demo-flag`)
4. Turn the flag ON and configure variations

## Integration with Dynatrace

The JSON logs are output to stdout and can be ingested by Dynatrace OneAgent or Operator for monitoring and observability.

## License

MIT

