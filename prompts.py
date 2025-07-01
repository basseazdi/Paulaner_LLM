"""config_campaignreporting.json_generator.prompts
=================================================
This module stores all reusable prompt templates and few shot examples
used by the *campaign‑reporting* pipeline.  They are imported by
`json_generator/main.py` (see the caller code in the user’s snippet).

Every string below is deliberately kept in **plain UTF‑8** with English
directives, because the LLM (Claude 3.5 Sonnet via Bedrock) performs best
when instructions are unambiguous and the evaluation criteria are crystal
clear.

# Variables exported
--------------------
- **rules**:      Master instruction set – ALWAYS prepend to a chat.
- **first_example**, **second_example**, **third_example**: user messages
  containing a ground‑truth JSON (`{json_X}`) and the JSON obtained from
  an Excel briefing (`{brf_X}`) so the model can learn the comparison
  task.  Each of these is paired with **expected_response_#**, which
  shows the ideal assistant answer.
- **new_request**: template used in production – placeholders
  `{clean_briefing}` and `{json}` will be filled at runtime.

The comparison logic focuses on the **most business‑critical sections**:
  * Start / end dates of the commercial activity.
  * Main description.
  * Success‑criteria list (including each metric’s *name*, *function*,
    *min_amount*, and *time window*).
  * Customer segmentation: must be either *null* or an explicit, valid
    segment object.

All example responses follow the same output convention so that the
calling code can parse them deterministically.
"""

###########################################################################
# 1. GLOBAL RULES ##########################################################
###########################################################################

rules: str = """
You are a *QA auditor* in charge of validating that two JSON documents   
representing the same marketing campaign are **semantically identical**.   
The 🟢 *reference JSON* comes from Adobe Campaign and is assumed to be
correct; the 🟠 *briefing JSON* was generated from an Excel sheet.  Your
job is to return a **bullet‑list of discrepancies** or the literal token
`NO_DIFF` when both documents match.

🔍 **Check the following elements (and nothing else):**
1. **commercial_activity.start_date** and **commercial_activity.end_date**   
   – must exist and be ISO formatted (`YYYY-MM-DD`).
2. **description** – plain‑text description of the action.  Ignore case and
   extra whitespace when comparing.
3. **success_criteria / metrics** – treat as an *unordered* list. Each
   entry must match on *metric_name*, *function*, *min_amount* (numeric),
   and *time_window*.
4. **customer_segmentation** – must be either `null` or a well‑formed
   object detailing the segment logic.  The two JSONs must agree.

⚙️ **Output format:**
- If there is **no difference**, respond with the single token `NO_DIFF`.
- Otherwise, one bullet per issue.  Use JSON‑path notation to locate the
  field, then a short description of the problem, e.g.:
  - 🔴 `commercial_activity.start_date`: expected `2025-08-01`, got `2025-07-30`
  - 🟠 `success_criteria[1].min_amount`: expected `500`, got `200`
- Use the icons **🔴** for blocking errors (dates, missing keys), **🟠** for
  warnings (description mismatch, additional keys).
- Keep the entire answer **under 1200 tokens**.
"""

###########################################################################
# 2. FEW‑SHOT EXAMPLES #####################################################
###########################################################################

# NOTE: the placeholders {json_1}, {brf_1}, etc. will be replaced at
# runtime with real documents so that the example remains reusable.

first_example: str = """
Below is **Example 1**. Compare the reference JSON to the briefing JSON
and answer following the *RULES*.

----------------  🟢  REFERENCE JSON  ----------------
{json_1}
----------------  🟠  BRIEFING JSON   ----------------
{brf_1}
"""

# In this example the two files are identical → expected response is
# simply NO_DIFF.
expected_response_1: str = """NO_DIFF"""

second_example: str = """
Below is **Example 2**. Compare the reference JSON to the briefing JSON
and answer following the *RULES*.

----------------  🟢  REFERENCE JSON  ----------------
{json_2}
----------------  🟠  BRIEFING JSON   ----------------
{brf_2}
"""

# Here we illustrate a *date* mismatch and a *min_amount* issue.
expected_response_2: str = """
- 🔴 `commercial_activity.start_date`: expected `2025-04-01`, got `2025-04-03`
- 🟠 `success_criteria[0].min_amount`: expected `300`, got `250`
"""

third_example: str = """
Below is **Example 3**. Compare the reference JSON to the briefing JSON
and answer following the *RULES*.

----------------  🟢  REFERENCE JSON  ----------------
{json_3}
----------------  🟠  BRIEFING JSON   ----------------
{brf_3}
"""

# This example focuses on *segmentation* and *description* differences.
expected_response_3: str = """
- 🟠 `description`: texts differ after normalisation
- 🔴 `customer_segmentation`: expected `null`, got an object defining a
      segment named *Clientes‑Alta* (should be null for an “Abierto”
      campaign)
"""

###########################################################################
# 3. RUNTIME REQUEST TEMPLATE #############################################
###########################################################################

# The pipeline fills the placeholders {clean_briefing} and {json} each
# time it needs a fresh comparison.

new_request: str = """
Please compare the two JSON documents below.  Use the **RULES** and return
`NO_DIFF` or a bullet list of discrepancies.

================  🟠  BRIEFING JSON   =================
{clean_briefing}
================  🟢  REFERENCE JSON  =================
{json}
"""
