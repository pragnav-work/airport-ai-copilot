# Uber Global Airport Operations & Supply Disruption Resolver

An agentic AI copilot for investigating airport operational issues, retrieving relevant airport policies, generating operational recommendations, validating proposed actions, and executing approved actions.

The project demonstrates an end-to-end AI application combining RAG, semantic search, operational tools, function calling, multi-agent reasoning, conversational memory, guardrails, human approval, audit logging, and a Streamlit interface.

## Project Objective

Airport operations teams need to respond quickly when operational metrics indicate supply or service disruptions.

This project provides an AI copilot that can:

- Investigate airport operational metrics
- Identify potential operational issues
- Retrieve relevant airport policies
- Generate operational recommendations
- Validate recommendations against policy rules
- Classify action risk
- Request human approval for high-risk actions
- Execute approved operational actions through mock tools
- Maintain conversational context
- Record the complete decision and execution trail

The supported airports are:

- SFO
- LAX
- JFK

## End-to-End Workflow

The application follows this workflow:

```text
User Query
    ↓
Intent Understanding
    ↓
Airport Resolution
    ↓
Investigation
    ↓
Policy Retrieval
    ↓
Agent Reasoning
    ↓
Recommendation
    ↓
Guardrail Validation
    ↓
Risk Classification
    ↓
Human Approval
    ↓
Action Execution
    ↓
Audit Trail
````

For policy-only questions, the system can retrieve the relevant policy information without performing an operational action.

## Project Architecture

```text
                    USER
                      │
                      ▼
                STREAMLIT APP
                      │
                      ▼
                INTENT ROUTING
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
    POLICY QUERY             ACTION QUERY
          │                       │
          ▼                       ▼
        RAG                 AGENT WORKFLOW
          │                       │
          ▼                       ▼
   VECTOR SEARCH            INVESTIGATION
                                  │
                                  ▼
                            POLICY RETRIEVAL
                                  │
                                  ▼
                           RECOMMENDATION
                                  │
                                  ▼
                            GUARDRAILS
                                  │
                                  ▼
                         HUMAN APPROVAL
                                  │
                                  ▼
                           MOCK EXECUTION
                                  │
                                  ▼
                            AUDIT TRAIL
```

## Repository Structure

```text
airport-ai-copilot/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app.py
│
├── data/
│   ├── airport_policies/
│   │   ├── sfo_operations.md
│   │   ├── sfo_pricing.md
│   │   ├── sfo_driver_policy.md
│   │   ├── lax_operations.md
│   │   ├── lax_pricing.md
│   │   ├── lax_driver_policy.md
│   │   ├── jfk_operations.md
│   │   ├── jfk_pricing.md
│   │   └── jfk_driver_policy.md
│   │
│   └── airport_metrics.csv
│
├── notebooks/
│   ├── day1_rag_pipeline.ipynb
│   ├── day2_tools.ipynb
│   ├── day3_agent.ipynb
│   └── day4_guardrails.ipynb
│
├── src/
│   ├── __init__.py
│   ├── agents.py
│   ├── guardrails.py
│   ├── memory.py
│   ├── prompts.py
│   └── tools.py
│
├── output/
│   └── distilled_training_data.jsonl
│
└── tests/
    ├── conftest.py
    ├── test_rag.py
    ├── test_tools.py
    └── test_guardrails.py
```

## Technology Stack

### Python

The core application is implemented in Python.

### Streamlit

Streamlit provides the interactive web application and chat interface.

### Gemini

Google Gemini is used for language-model reasoning, response generation, and function-calling workflows.

### Sentence Transformers

`all-MiniLM-L6-v2` is used to convert policy text and user queries into vector embeddings.

The model produces 384-dimensional embeddings.

### FAISS

FAISS is used for vector similarity search.

The project uses normalized embeddings with an inner-product index, allowing similarity search over the policy knowledge base.

### Pandas

Pandas is used to load and process the synthetic airport operational dataset.

### Pytest

Pytest is used to validate RAG, operational tools, and guardrail behavior.

## RAG Pipeline

The policy knowledge base contains synthetic airport policies covering:

* Airport operations
* Pricing and surge rules
* Driver policies

The RAG pipeline follows:

```text
Policy Documents
      ↓
Text Loading
      ↓
Chunking
      ↓
Sentence Transformer
      ↓
384-Dimensional Embeddings
      ↓
Normalization
      ↓
FAISS Index
      ↓
Semantic Search
      ↓
Relevant Policy Context
      ↓
Gemini Response
```

Policy documents are chunked before embedding so that relevant sections can be retrieved instead of sending complete documents to the model.

The system also applies airport-specific filtering so that a query for one airport retrieves the relevant airport policy information.

## Operational Dataset

The synthetic operational dataset contains airport-level metrics such as:

* Completion rate
* Average ETA
* Active drivers
* Driver cancellation rate
* Queue size
* Surge multiplier

The operational investigation uses the latest available record for the selected airport.

## Operational Tools

The project implements three operational tools.

### 1. Airport Metrics Tool

Retrieves the latest operational metrics for:

```text
SFO
LAX
JFK
```

### 2. Driver Incentive Tool

Calculates a recommended driver incentive based on:

```text
driver count
severity level
```

Severity levels are:

```text
low
medium
high
```

### 3. Surge Override Tool

Simulates a surge-price override.

The tool validates:

* Airport code
* Surge multiplier range
* Reason for the override

The action is a mock execution and does not modify a real production system.

## Function Calling

Gemini function calling is used to allow the model to select appropriate operational tools based on the user request.

The application maps function names to the corresponding Python tool implementations.

Example:

```text
User Request
     ↓
Gemini
     ↓
Function Selection
     ↓
Python Tool
     ↓
Tool Result
     ↓
Gemini
     ↓
Final Response
```

## Multi-Agent Workflow

The agent workflow separates the operational reasoning process into specialized responsibilities.

### Orchestrator

Coordinates the overall workflow.

### Operations Investigator

Examines airport metrics and identifies operational severity.

### Policy Agent

Retrieves relevant airport policy information using semantic search.

### Resolution Agent

Uses operational evidence and retrieved policy context to generate a recommended resolution.

This separation makes the reasoning workflow easier to inspect and trace.

## ReAct-Style Execution Loop

The project includes a simplified ReAct-style execution loop.

The workflow repeatedly evaluates the required next step:

```text
Investigate
    ↓
Retrieve Policy
    ↓
Generate Recommendation
    ↓
Validate
    ↓
Stop
```

The loop has a maximum iteration limit to prevent uncontrolled execution.

## Conversational Memory

The application maintains lightweight conversational memory.

The memory stores:

* Last airport
* Last user query
* Last investigation

This allows follow-up requests to use information from the previous interaction.

For example:

```text
User: Increase surge at SFO.

Assistant: What multiplier would you like?

User: 1.4x
```

The second message can be interpreted using the previous action context rather than being treated as an unrelated request.

## Guardrails

Operational actions pass through guardrails before execution.

The guardrail layer performs:

1. Permission validation
2. Required parameter validation
3. Policy validation
4. Risk classification
5. Human approval validation
6. Execution control

Invalid or policy-violating actions are blocked.

## Risk Classification

Surge actions are classified based on the requested multiplier.

The current rule is:

```text
Below 1.3x
    → Low risk
    → No approval required

1.3x or higher
    → High risk
    → Human approval required

Above airport policy maximum
    → Blocked
```

Airport policy limits are applied before execution.

## Human-in-the-Loop Approval

High-risk actions cannot execute automatically.

For example:

```text
Requested Action:
Increase SFO surge to 1.4x

Risk Level:
HIGH

Human Approval:
REQUIRED
```

The action is executed only after an authorized user approves it.

This prevents the agent from independently executing high-risk operational changes.

## Audit Trail

The application records the decision and execution process.

The audit trail captures information including:

* User request
* Agents invoked
* Tools called
* Retrieved policies
* Recommendation
* Risk level
* User role
* Airport
* Requested multiplier
* Reason
* Approval decision
* Guardrail status
* Final action
* Execution status

This provides traceability for operational decisions.

## Distilled Training Data

The project also produces structured interaction records in:

```text
output/distilled_training_data.jsonl
```

The records contain fields such as:

```text
instruction
context
tool_calls
recommendation
policy_check
human_approval
final_action
```

The dataset demonstrates how agent interactions can be converted into structured training or distillation examples.

Fine-tuning a model is not required for this project.

## Streamlit Application

Run the application with:

```bash
streamlit run app.py
```

The interface provides:

* Airport selector
* Natural-language chat
* Operational metrics
* Agent activity trace
* RAG trace
* Recommendation details
* Human approval workflow
* Execution result
* Audit information

Supported airports:

```text
SFO
LAX
JFK
```

## Example Operational Flow

Example request:

```text
Investigate SFO. Completion rate appears to be low.
Can we increase surge to 1.5x?
```

The system can follow this flow:

```text
1. Investigate airport metrics
2. Identify operational anomaly
3. Identify contributing factors
4. Retrieve SFO pricing policy
5. Generate recommendation
6. Validate the recommendation
7. Classify risk as HIGH
8. Request human approval
9. Execute the approved mock action
10. Record the complete audit trail
```

The final response communicates the chain:

```text
Issue
  ↓
Evidence
  ↓
Policy
  ↓
Recommendation
  ↓
Risk Check
  ↓
Approval
  ↓
Action
```

## Policy Query Example

The application also supports policy questions that do not require an operational action.

Example:

```text
What is the maximum surge allowed at SFO?
```

The system:

```text
User Question
     ↓
Intent Classification
     ↓
Policy Retrieval
     ↓
Relevant SFO Policy
     ↓
Gemini
     ↓
Policy Answer
```

No operational action is executed for a policy-only query.

## Testing

Run the complete test suite with:

```bash
pytest -v
```

The tests cover:

* RAG behavior
* Operational tools
* Guardrails
* Permissions
* Policy validation
* Risk classification
* Human approval behavior
* Invalid input handling

## Environment Setup

Create and activate the project virtual environment, then install the dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file containing the Gemini API key:

```text
GEMINI_API_KEY=your_api_key_here
```

Do not commit the real `.env` file to Git.

## Certificate Configuration

On systems where Hugging Face model downloads encounter certificate issues, the project uses the following certificate configuration before loading the embedding model:

```python
# Certificate issue resolve

import os

os.environ["REQUESTS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-certificates.crt"
```

## Project Learning Journey

```text
Day 1
Git + Prompt Engineering + RAG + Embeddings + Vector Search
        ↓
Day 2
Operational Data + Tools + Function Calling
        ↓
Day 3
Multi-Agent System + ReAct + Memory
        ↓
Day 4
Guardrails + Policy Validation + Human-in-the-Loop
        ↓
Day 5
Streamlit + End-to-End AI Copilot + Final Demo
```

## Key Learning Outcomes

This project demonstrates practical understanding of:

* Retrieval-Augmented Generation
* Embeddings
* Semantic search
* FAISS vector databases
* LLM function calling
* Tool-based agents
* Multi-agent workflows
* ReAct-style reasoning
* Conversational memory
* Input and action validation
* Policy enforcement
* Risk classification
* Human-in-the-loop systems
* Auditability
* Distilled interaction datasets
* Streamlit application development
* End-to-end AI system integration

## Limitations

This is a synthetic demonstration project.

* Airport operational data is synthetic.
* Airport policies are synthetic.
* Operational actions are mock executions.
* No real airport systems are modified.
* Human approval is represented within the application workflow.
* The system should not be used for real operational decisions without appropriate production validation, security, monitoring, and authorization controls.

