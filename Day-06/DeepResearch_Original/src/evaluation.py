import os
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langsmith import Client
from pydantic import BaseModel, Field

conversation_1 = [
    HumanMessage(content="What's the best way to invest $50,000 for retirement?"),
    AIMessage(
        content="Could you please provide some additional information to tailor the investment advice for your $50,000 retirement goal? Specifically:\n Your current age or desired retirement age\n Your risk tolerance (low, medium, high)\n Any preferences for investment types (e.g., stocks, bonds, mutual funds, real estate)\n Whether you are investing through a tax-advantaged account (e.g., IRA, 401(k)) or a regular brokerage account\n This will help me provide more personalized and relevant suggestions."
    ),
    HumanMessage(
        content="I'm 25 and I want to retire by 45. My risk tolerance is high right now but I think will decrease over time. I have heard that stocks and ETFs are a good choice, but I'm open to anything. And I already have a 401k, but this would just be through a regular brokerage account."
    ),
]

conversation_2 = [
    HumanMessage(content="I am looking for an apartment in NYC, can you help me?"),
    AIMessage(
        content="Could you please specify your apartment preferences? For example:\n Desired neighborhoods or boroughs\n Number of bedrooms/bathrooms\n Budget range (monthly rent)\n Any amenities or must-have features\n Preferred move-in date\n This information will help me provide the most relevant apartment options in NYC."
    ),
    HumanMessage(
        content="I'd prefer to live in Chelsea, Flatiron, or West Village. I'm looking for a 2 bed 2 bath, and I am looking for monthly rent below 7k. I'd like this to be a doorman building and have an in unit washer and dryer, but it's okay if there's no washer dryer. It's a plus if the building has a gym. And I'd like to move in in September 2025."
    ),
]

criteria_1 = [
    "Current age is 25",
    "Desired retirement age is 45",
    "Current risk tolerance is high",
    "Interested in investing in stocks and ETFs",
    "Open to forms of investment beyond stocks and ETFs"
    "Investment account is a regular brokerage account",
]

criteria_2 = [
    "Looking for a 2 bed 2 bath apartment in Chelsea, Flatiron, or West Village",
    "Monthly rent below 7k",
    "Should be in a doorman building",
    "Ideally have an in unit washer and dryer but not strict",
    "Ideally have a gym but not strict",
    "Move in date is September 2025",
]

# Initialize the LangSmith client
langsmith_client = Client(api_key=os.getenv("LANGSMITH_API_KEY"))

# Create the dataset
dataset_name = "deep_research_scoping"
if not langsmith_client.has_dataset(dataset_name=dataset_name):
    # Create the dataset
    dataset = langsmith_client.create_dataset(
        dataset_name=dataset_name,
        description="A dataset that measures the quality of research briefs generated from an input conversation",
    )

    # Add the examples to the dataset
    langsmith_client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {
                "inputs": {"messages": conversation_1},
                "outputs": {"criteria": criteria_1},
            },
            {
                "inputs": {"messages": conversation_2},
                "outputs": {"criteria": criteria_2},
            },
        ],
    )


"""
For this, we'll use an LLM-as-judge. You can fine some useful tips for writing llm-as-judge evaluators here, which include:

Role Definition with Expertise Context

Defined specific expert roles ("research brief evaluator", "meticulous auditor")
Specialized the role to the specific evaluation domain
Clear Task Specification

Binary pass/fail judgments (avoiding complex multi-dimensional scoring)
Explicit task boundaries and objectives
Focus on actionable evaluation criteria
Rich Contextual Background

Provide domain-specific context about research brief quality
Explain the importance of accurate evaluation
Connect evaluation outcomes to downstream consequences
Structured XML Organization

Used semantic XML tags for different sections
Clear separation of role, task, context, inputs, guidelines, and outputs
Improved prompt parsing and comprehension
Comprehensive Guidelines with Examples

Detailed PASS/FAIL criteria with specific conditions
Multiple concrete examples showing correct judgments
3-4 examples per prompt covering different scenarios
Both positive and negative examples for each judgment type
Edge case handling and decision boundary clarification
Explicit Output Instructions

Clear guidance on how to apply the evaluation criteria
Instructions for handling ambiguous cases
Emphasis on consistency and systematic evaluation
Bias Reduction Techniques

"Strict but fair" guidance to balance precision and recall
"When in doubt, lean toward FAIL" for conservative evaluation
Systematic evaluation process to reduce subjective variation
"""


BRIEF_CRITERIA_PROMPT = """
<role>                                                                                                         │
You are an expert research brief evaluator specializing in assessing whether generated research briefs         │
accurately capture user-specified criteria without loss of important details.                                  │
</role>                                                                                                        │

<task>                                                                                                         │
Determine if the research brief adequately captures the specific success criterion provided. Return a binary   │
assessment with detailed reasoning.                                                                            │
</task>                                                                                                        │

<evaluation_context>                                                                                           │
Research briefs are critical for guiding downstream research agents. Missing or inadequately captured          │
criteria can lead to incomplete research that fails to address user needs. Accurate evaluation ensures         │
research quality and user satisfaction.                                                                        │
</evaluation_context>                                                                                          │

<criterion_to_evaluate>                                                                                        │
{criterion}                                                                                                    │
</criterion_to_evaluate>                                                                                       │

<research_brief>                                                                                               │
{research_brief}                                                                                               │
</research_brief>                                                                                              │

<evaluation_guidelines>                                                                                        │
CAPTURED (criterion is adequately represented) if:                                                             │
- The research brief explicitly mentions or directly addresses the criterion                                   │
- The brief contains equivalent language or concepts that clearly cover the criterion                          │
- The criterion's intent is preserved even if worded differently                                               │
- All key aspects of the criterion are represented in the brief                                                │

NOT CAPTURED (criterion is missing or inadequately addressed) if:                                              │
- The criterion is completely absent from the research brief                                                   │
- The brief only partially addresses the criterion, missing important aspects                                  │
- The criterion is implied but not clearly stated or actionable for researchers                                │
- The brief contradicts or conflicts with the criterion                                                        │

<evaluation_examples>                                                                                          │
Example 1 - CAPTURED:                                                                                          │
Criterion: "Current age is 25"                                                                                 │
Brief: "...investment advice for a 25-year-old investor..."                                                    │
Judgment: CAPTURED - age is explicitly mentioned                                                               │

Example 2 - NOT CAPTURED:                                                                                      │
Criterion: "Monthly rent below 7k"                                                                             │
Brief: "...find apartments in Manhattan with good amenities..."                                                │
Judgment: NOT CAPTURED - budget constraint is completely missing                                               │

Example 3 - CAPTURED:                                                                                          │
Criterion: "High risk tolerance"                                                                               │
Brief: "...willing to accept significant market volatility for higher returns..."                              │
Judgment: CAPTURED - equivalent concept expressed differently                                                  │

Example 4 - NOT CAPTURED:                                                                                      │
Criterion: "Doorman building required"                                                                         │
Brief: "...find apartments with modern amenities..."                                                           │
Judgment: NOT CAPTURED - specific doorman requirement not mentioned                                            │
</evaluation_examples>                                                                                         │
</evaluation_guidelines>                                                                                       │

<output_instructions>                                                                                          │
1. Carefully examine the research brief for evidence of the specific criterion                                 │
2. Look for both explicit mentions and equivalent concepts                                                     │
3. Provide specific quotes or references from the brief as evidence                                            │
4. Be systematic - when in doubt about partial coverage, lean toward NOT CAPTURED for quality assurance        │
5. Focus on whether a researcher could act on this criterion based on the brief alone                          │
</output_instructions>
"""


class Criteria(BaseModel):
    """Individual success criteria evaluation result.

    This model represents a single evaluation criteria that should be present
    in the research brief, along with a detailed assessment of whether it was
    successfully captured and the reasoning behind that assessment.
    """

    criteria_text: str = Field(
        description="The specific success criteria being evaluated (e.g., 'Current age is 25', 'Monthly rent below 7k')"
    )
    reasoning: str = Field(
        description="Detailed explanation of why this criteria is or isn't captured in the research brief, including specific evidence from the brief"
    )
    is_captured: bool = Field(
        description="Whether this specific criteria is adequately captured in the research brief (True) or missing/inadequately addressed (False)"
    )


def evaluate_success_criteria(outputs: dict, reference_outputs: dict):
    """Evaluate whether the research brief captures all required success criteria.

    This function evaluates each criterion individually to provide focused assessment
    and detailed reasoning for each evaluation decision.

    Args:
        outputs: Dictionary containing the research brief to evaluate
        reference_outputs: Dictionary containing the list of success criteria

    Returns:
        Dict with evaluation results including score (0.0 to 1.0)
    """
    research_brief = outputs["research_brief"]
    success_criteria = reference_outputs["criteria"]

    model = ChatOpenAI(model="gpt-4.1", temperature=0)
    structured_output_model = model.with_structured_output(Criteria)

    # Run evals
    responses = structured_output_model.batch(
        [
            [
                HumanMessage(
                    content=BRIEF_CRITERIA_PROMPT.format(
                        research_brief=research_brief, criterion=criterion
                    )
                )
            ]
            for criterion in success_criteria
        ]
    )

    # Ensure the criteria_text field is populated correctly
    individual_evaluations = [
        Criteria(
            reasoning=response.reasoning, criteria_text=criterion, is_captured=response.is_captured
        )
        for criterion, response in zip(success_criteria, responses)
    ]

    # Calculate overall score as percentage of captured criteria
    captured_count = sum(1 for eval_result in individual_evaluations if eval_result.is_captured)
    total_count = len(individual_evaluations)

    return {
        "key": "success_criteria_score",
        "score": captured_count / total_count if total_count > 0 else 0.0,
        "individual_evaluations": [
            {
                "criteria": eval_result.criteria_text,
                "captured": eval_result.is_captured,
                "reasoning": eval_result.reasoning,
            }
            for eval_result in individual_evaluations
        ],
    }


BRIEF_HALLUCINATION_PROMPT = """
## Brief Hallucination Evaluator

<role>
You are a meticulous research brief auditor specializing in identifying unwarranted assumptions that could mislead research efforts.
</role>

<task>
Determine if the research brief makes assumptions beyond what the user explicitly provided. Return a binary pass/fail judgment.
</task>

<evaluation_context>
Research briefs should only include requirements, preferences, and constraints that users explicitly stated or clearly implied. Adding assumptions can lead to research that misses the user's actual needs.
</evaluation_context>

<research_brief>
{research_brief}
</research_brief>

<success_criteria>
{success_criteria}
</success_criteria>

<evaluation_guidelines>
PASS (no unwarranted assumptions) if:
- Brief only includes explicitly stated user requirements
- Any inferences are clearly marked as such or logically necessary
- Source suggestions are general recommendations, not specific assumptions
- Brief stays within the scope of what the user actually requested

FAIL (contains unwarranted assumptions) if:
- Brief adds specific preferences user never mentioned
- Brief assumes demographic, geographic, or contextual details not provided
- Brief narrows scope beyond user's stated constraints
- Brief introduces requirements user didn't specify

<evaluation_examples>
Example 1 - PASS:
User criteria: ["Looking for coffee shops", "In San Francisco"]
Brief: "...research coffee shops in San Francisco area..."
Judgment: PASS - stays within stated scope

Example 2 - FAIL:
User criteria: ["Looking for coffee shops", "In San Francisco"]
Brief: "...research trendy coffee shops for young professionals in San Francisco..."
Judgment: FAIL - assumes "trendy" and "young professionals" demographics

Example 3 - PASS:
User criteria: ["Budget under $3000", "2 bedroom apartment"]
Brief: "...find 2-bedroom apartments within $3000 budget, consulting rental sites and local listings..."
Judgment: PASS - source suggestions are appropriate, no preference assumptions

Example 4 - FAIL:
User criteria: ["Budget under $3000", "2 bedroom apartment"]
Brief: "...find modern 2-bedroom apartments under $3000 in safe neighborhoods with good schools..."
Judgment: FAIL - assumes "modern", "safe", and "good schools" preferences
</evaluation_examples>
</evaluation_guidelines>

<output_instructions>
Carefully scan the brief for any details not explicitly provided by the user. Be strict - when in doubt about whether something was user-specified, lean toward FAIL.
</output_instructions>"""


# Improved NoAssumptions class with reasoning field and enhanced descriptions
class NoAssumptions(BaseModel):
    """Evaluation model for checking if research brief makes unwarranted assumptions.

    This model evaluates whether the research brief contains any assumptions,
    inferences, or additions that were not explicitly stated by the user in their
    original conversation. It provides detailed reasoning for the evaluation decision.
    """

    no_assumptions: bool = Field(
        description="Whether the research brief avoids making unwarranted assumptions. True if the brief only includes information explicitly provided by the user, False if it makes assumptions beyond what was stated."
    )
    reasoning: str = Field(
        description="Detailed explanation of the evaluation decision, including specific examples of any assumptions found or confirmation that no assumptions were made beyond the user's explicit statements."
    )


def evaluate_no_assumptions(outputs: dict, reference_outputs: dict):
    """Evaluate whether the research brief avoids making unwarranted assumptions.

    This evaluator checks that the research brief only includes information
    and requirements that were explicitly provided by the user, without
    making assumptions about unstated preferences or requirements.

    Args:
        outputs: Dictionary containing the research brief to evaluate
        reference_outputs: Dictionary containing the success criteria for reference

    Returns:
        Dict with evaluation results including boolean score and detailed reasoning
    """
    research_brief = outputs["research_brief"]
    success_criteria = reference_outputs["criteria"]

    model = ChatOpenAI(model="gpt-4.1", temperature=0)
    structured_output_model = model.with_structured_output(NoAssumptions)

    response = structured_output_model.invoke(
        [
            HumanMessage(
                content=BRIEF_HALLUCINATION_PROMPT.format(
                    research_brief=research_brief, success_criteria=str(success_criteria)
                )
            )
        ]
    )

    return {
        "key": "no_assumptions_score",
        "score": response.no_assumptions,
        "reasoning": response.reasoning,
    }


def target_func(inputs: dict):
    config = {"configurable": {"thread_id": uuid.uuid4()}}
    return scope.invoke(inputs, config=config)


langsmith_client.evaluate(
    target_func,
    data=dataset_name,
    evaluators=[evaluate_success_criteria, evaluate_no_assumptions],
    experiment_prefix="Deep Research Scoping",
)
