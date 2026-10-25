"""Typed node / edge vocabulary. Both lists are open: unknown types are accepted with a warning
so the schema can grow, but known types get validation and stable semantics."""

from __future__ import annotations

NODE_TYPES = {
    "Paper": "A publication or preprint version (canonical id = DOI > arXiv > PMID > ...)",
    "Author": "Author",
    "Venue": "Journal / conference / repository",
    "ResearchProblem": "Scientific or technical problem a work addresses",
    "ScientificClaim": "A claim made by a paper, a project or the agent",
    "Method": "A concrete method / model (e.g. a named architecture)",
    "Mechanism": "Abstract mechanism class (e.g. optimal transport); may be discovered dynamically",
    "MathematicalOperator": "Core operator (e.g. Sinkhorn iteration, message passing, Fourier layer)",
    "InductiveBias": "Inductive bias introduced or relied upon",
    "Assumption": "Assumption a method or analysis depends on",
    "Domain": "Discipline / application domain",
    "Dataset": "Dataset (with version)",
    "DataProcessingStep": "Filtering / normalization / split / augmentation step",
    "EvaluationProtocol": "Protocol: split, aggregation level, metric computation",
    "Metric": "Metric definition from the metric ontology",
    "ExperimentalResult": "A reported or observed result",
    "Limitation": "Limitation (author-acknowledged, inferred, or agent-proposed)",
    "FailureMode": "Observed or reported failure pattern",
    "GitHubRepository": "Source repository",
    "CodeModule": "File / function / class in a pinned repository commit",
    "MethodSignature": "Transferable abstraction of a method",
    "ProblemStructure": "Abstract problem structure shared across domains",
    "TransferHypothesis": "Candidate cross-domain transfer (always hypothesis until tested)",
    "ResearchIdea": "Innovation candidate / research idea",
    "Project": "Local research project",
    "LocalExperiment": "Experiment executed in a local project",
    "Diagnosis": "Literature-guided diagnosis worksheet",
    "Topic": "Watched topic for incremental refresh",
}

EDGE_TYPES = {
    "SOLVES", "USES_METHOD", "USES_MECHANISM", "INTRODUCES_MECHANISM", "EXTENDS", "CONTRADICTS", "SUPPORTS",
    "EVALUATED_ON", "MEASURED_BY", "HAS_LIMITATION", "DEPENDS_ON_ASSUMPTION", "IMPLEMENTED_BY", "HAS_CODE_MODULE",
    "SHARES_MECHANISM_WITH", "POTENTIALLY_TRANSFERS_TO", "EXPLAINS_FAILURE", "INSPIRES_HYPOTHESIS", "CITES",
    "VERSION_OF", "AUTHORED_BY", "PUBLISHED_IN", "IN_DOMAIN", "HAS_SIGNATURE", "INSTANCE_OF_STRUCTURE",
    "SUBCLASS_OF", "VIOLATES_ASSUMPTION", "SATISFIES_ASSUMPTION", "TESTS", "OBSERVED_IN", "PART_OF_PROJECT",
    "LINKS_TO", "USES_OPERATOR", "HAS_INDUCTIVE_BIAS", "MAKES_CLAIM", "REPORTS_RESULT", "HAS_FAILURE_MODE",
    "USES_DATASET", "HAS_PROCESSING_STEP",
}

# Nodes that describe a local project live in the project store; everything else is global knowledge.
PROJECT_TYPES = {"Project", "LocalExperiment", "Diagnosis"}

PREFIX = {t: t[0].lower() + t[1:] for t in NODE_TYPES}
PREFIX.update({"Paper": "paper", "GitHubRepository": "repo", "CodeModule": "code", "Mechanism": "mechanism",
               "MathematicalOperator": "operator", "InductiveBias": "bias", "Assumption": "assumption",
               "ResearchProblem": "problem", "ScientificClaim": "claim", "ExperimentalResult": "result",
               "Limitation": "limitation", "FailureMode": "failure", "MethodSignature": "signature",
               "ProblemStructure": "structure", "TransferHypothesis": "transfer", "ResearchIdea": "idea",
               "LocalExperiment": "experiment", "EvaluationProtocol": "protocol",
               "DataProcessingStep": "step"})
TYPE_OF_PREFIX = {v: k for k, v in PREFIX.items()}


def type_from_id(node_id: str):
    return TYPE_OF_PREFIX.get(node_id.split(":", 1)[0])
