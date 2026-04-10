# Skills Specification

## Core Skills (agent_core/skills/builtin.py)

### ParserSkill
**Name**: `parser`
**Purpose**: Rule-based parser that extracts retrieval text and arithmetic 
expressions from the raw query.
**Input**: Raw query string
**Output**: Artifact of type `parsed_query` with fields:
- `original_query`: original question
- `retrieval_query`: cleaned query for retrieval
- `calculation_expression`: math expression if found
- `needs_retrieval`: boolean
- `needs_calculation`: boolean

---

### LLMQueryParserSkill
**Name**: `llm_query_parser`
**Purpose**: LLM-driven parser that converts raw query into structured slots.
**Input**: Raw query string
**Output**: Artifact of type `parsed_query` (same fields as ParserSkill)
**Note**: Only activates when LLM endpoint is available. Falls back to 
rule-based parser if LLM fails.

---

### RetrievalSkill
**Name**: `retrieval`
**Purpose**: Keyword-based retrieval over mock documents.
**Input**: Artifact of type `parsed_query`
**Output**: Artifact of type `retrieval_result` with fields:
- `doc_id`: document identifier
- `title`: document title
- `snippet`: relevant text from document

---

### CalculatorSkill
**Name**: `calculator`
**Purpose**: Deterministic arithmetic evaluator for simple expressions.
**Input**: Artifact of type `parsed_query` containing `calculation_expression`
**Output**: Artifact of type `calculation_result` with fields:
- `expression`: the math expression
- `value`: computed result
**Note**: Uses safe AST evaluation — no use of Python eval().

---

### ReportWriterSkill
**Name**: `report_writer`
**Purpose**: Template-based deterministic report writer.
**Input**: Artifacts of type `retrieval_result` and/or `calculation_result`
**Output**: Artifact of type `report` with fields:
- `answer`: final answer string
- `summary`: short summary
- `evidence_ids`: list of artifact IDs used as evidence

---

### LLMReportWriterSkill
**Name**: `llm_report_writer`
**Purpose**: LLM-driven report writer that produces final JSON response.
**Input**: Artifacts of type `retrieval_result` and/or `calculation_result`
**Output**: Artifact of type `report` (same fields as ReportWriterSkill)
**Note**: Only activates when LLM endpoint is available. Falls back to 
rule-based report writer if LLM fails.

---

### UnitNormalizerSkill
**Name**: `unit_normalizer`
**Purpose**: Converts financial text values to plain floats.
**Input**: Artifact of type `parsed_query`
**Output**: Artifact of type `normalized_value` with fields:
- `raw`: original text
- `value`: converted float
**Examples**:
- `"$1.2 billion"` → `1200000000.0`
- `"3.5%"` → `0.035`
- `"500M"` → `500000000.0`

---

## Extraction Utilities (agent_core/skills/extractors.py)

### extract_number(text)
**Purpose**: Pulls the first meaningful number from text.
**Input**: Any text string
**Output**: float or None
**Examples**:
- `"507 million dollars"` → `507000000.0`
- `"3.5 percent"` → `0.035`
- `"Page 42"` → `42.0`

---

### extract_date(text)
**Purpose**: Pulls year and optional month from text.
**Input**: Any text string
**Output**: tuple (year, month) or None
**Examples**:
- `"January 1985"` → `(1985, 1)`
- `"Fiscal Year 1934"` → `(1934, None)`
- `"December 1998"` → `(1998, 12)`

---

### extract_table_value(text, label)
**Purpose**: Finds a labeled value in a table row.
**Input**: Text string and label to search for
**Output**: float or None
**Examples**:
- `text="Veterans Administration: 507", label="Veterans Administration"` 
  → `507.0`