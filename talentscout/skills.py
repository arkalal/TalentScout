"""Skill taxonomy: canonical skill names, aliases and a matcher.

Shared by the resume generator, the resume parser and the scorer so that
"React.js", "ReactJS" and "React" all count as the same skill.
"""

from __future__ import annotations

import re
from functools import lru_cache

# canonical name -> list of alias regexes (matched case-insensitively unless prefixed with "(?-i)")
SKILL_ALIASES: dict[str, list[str]] = {
    # languages
    "Python": [r"python"],
    "Java": [r"java(?!\s*script)"],
    "JavaScript": [r"javascript", r"(?-i:JS)", r"ES6"],
    "TypeScript": [r"typescript", r"(?-i:TS)"],
    "Go": [r"golang", r"(?-i:Go)(?![-\w])"],
    "Rust": [r"rust"],
    "C++": [r"c\+\+"],
    "C#": [r"c#"],
    "Kotlin": [r"kotlin"],
    "Swift": [r"swift(?:ui)?"],
    "Ruby": [r"ruby(?! on rails)"],
    "Ruby on Rails": [r"ruby on rails", r"rails"],
    "PHP": [r"php"],
    "Scala": [r"scala"],
    "SQL": [r"sql(?!ite)"],
    "Dart": [r"dart"],
    # frontend
    "React": [r"react(?:\.js|js)?(?!\s*native)"],
    "Next.js": [r"next\.?js"],
    "Redux": [r"redux"],
    "Vue.js": [r"vue(?:\.js|js)?"],
    "Angular": [r"angular(?:js)?"],
    "HTML": [r"html5?"],
    "CSS": [r"css3?", r"sass", r"scss"],
    "Tailwind CSS": [r"tailwind(?:\s*css)?"],
    "Webpack": [r"webpack", r"vite"],
    "Jest": [r"jest"],
    "Cypress": [r"cypress"],
    "GraphQL": [r"graphql"],
    "React Native": [r"react\s*native"],
    "Flutter": [r"flutter"],
    # backend
    "Node.js": [r"node\.?js"],
    "Express": [r"express(?:\.js)?"],
    "Django": [r"django"],
    "Flask": [r"flask"],
    "FastAPI": [r"fastapi"],
    "Spring Boot": [r"spring\s*boot"],
    "REST APIs": [r"rest(?:ful)?\s*apis?", r"rest(?:ful)? services"],
    "Microservices": [r"micro-?services"],
    "gRPC": [r"grpc"],
    "Kafka": [r"kafka"],
    "RabbitMQ": [r"rabbitmq"],
    "Redis": [r"redis"],
    "PostgreSQL": [r"postgres(?:ql)?"],
    "MySQL": [r"mysql"],
    "MongoDB": [r"mongo(?:db)?"],
    "Elasticsearch": [r"elastic\s*search"],
    "DynamoDB": [r"dynamo\s*db"],
    # cloud / devops
    "AWS": [r"aws", r"amazon web services"],
    "GCP": [r"gcp", r"google cloud"],
    "Azure": [r"azure"],
    "Docker": [r"docker"],
    "Kubernetes": [r"kubernetes", r"k8s", r"(?-i:EKS|GKE|AKS)"],
    "Terraform": [r"terraform"],
    "Infrastructure as Code": [r"infrastructure[- ]as[- ]code", r"(?-i:IaC)", r"terraform", r"cloudformation", r"pulumi"],
    "Jenkins": [r"jenkins"],
    "GitHub Actions": [r"github actions"],
    "CI/CD": [r"ci/cd", r"continuous (?:integration|delivery|deployment)"],
    "Linux": [r"linux"],
    "Prometheus": [r"prometheus"],
    "Grafana": [r"grafana"],
    "Ansible": [r"ansible"],
    # data / ML
    "Pandas": [r"pandas"],
    "NumPy": [r"numpy"],
    "Scikit-learn": [r"scikit-?learn", r"sklearn"],
    "TensorFlow": [r"tensorflow", r"keras"],
    "PyTorch": [r"pytorch"],
    "Spark": [r"(?:apache\s*)?spark", r"pyspark"],
    "Airflow": [r"airflow"],
    "dbt": [r"(?-i:dbt)"],
    "Snowflake": [r"snowflake"],
    "Tableau": [r"tableau"],
    "Power BI": [r"power\s*bi"],
    "Machine Learning": [r"machine learning", r"(?-i:ML)(?![-\w])"],
    "Deep Learning": [r"deep learning"],
    "NLP": [r"nlp", r"natural language processing"],
    "LLMs": [r"llms?", r"large language models?", r"generative ai", r"genai"],
    "LangChain": [r"langchain", r"langgraph"],
    "Computer Vision": [r"computer vision", r"opencv"],
    "Statistics": [r"statistics", r"statistical"],
    "A/B Testing": [r"a/b test(?:ing|s)?", r"experimentation"],
    # mobile
    "Android": [r"android"],
    "iOS": [r"ios"],
    # QA
    "Selenium": [r"selenium"],
    "Playwright": [r"playwright"],
    "Appium": [r"appium"],
    "JUnit": [r"junit"],
    "Pytest": [r"pytest"],
    # practices
    "System Design": [r"system design", r"distributed systems"],
    "Agile": [r"agile", r"scrum"],
}

SKILL_CATEGORIES: dict[str, list[str]] = {
    "Languages": ["Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#", "Kotlin",
                  "Swift", "Ruby", "PHP", "Scala", "SQL", "Dart"],
    "Frontend": ["React", "Next.js", "Redux", "Vue.js", "Angular", "HTML", "CSS", "Tailwind CSS",
                 "Webpack", "Jest", "Cypress", "GraphQL", "React Native", "Flutter"],
    "Backend": ["Node.js", "Express", "Django", "Flask", "FastAPI", "Spring Boot", "REST APIs",
                "Microservices", "gRPC", "Kafka", "RabbitMQ", "Redis", "PostgreSQL", "MySQL",
                "MongoDB", "Elasticsearch", "DynamoDB", "Ruby on Rails"],
    "Cloud/DevOps": ["AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Infrastructure as Code", "Jenkins",
                     "GitHub Actions", "CI/CD", "Linux", "Prometheus", "Grafana", "Ansible"],
    "Data/ML": ["Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch", "Spark", "Airflow", "dbt",
                "Snowflake", "Tableau", "Power BI", "Machine Learning", "Deep Learning", "NLP", "LLMs",
                "LangChain", "Computer Vision", "Statistics", "A/B Testing"],
    "Mobile": ["Android", "iOS"],
    "QA": ["Selenium", "Playwright", "Appium", "JUnit", "Pytest"],
    "Practices": ["System Design", "Agile"],
}


def _compile(alias: str) -> re.Pattern:
    # word-ish boundaries that also work for skills ending in symbols (C++, C#, Next.js)
    return re.compile(rf"(?<![\w+#.]){alias}(?![\w+#])", re.IGNORECASE)


@lru_cache(maxsize=1)
def _patterns() -> dict[str, list[re.Pattern]]:
    return {name: [_compile(a) for a in aliases] for name, aliases in SKILL_ALIASES.items()}


def find_skills(text: str) -> set[str]:
    """Return the canonical skills mentioned anywhere in ``text``."""
    return {name for name, pats in _patterns().items() if any(p.search(text) for p in pats)}


def normalize_skill(raw: str) -> str:
    """Map a free-text skill ("ReactJS", "k8s") to its canonical name; unknown skills are returned title-stripped."""
    raw = raw.strip()
    for name in SKILL_ALIASES:
        if raw.lower() == name.lower():
            return name
    for name, pats in _patterns().items():
        if any(p.fullmatch(raw) for p in pats):
            return name
    hits = find_skills(raw)
    if len(hits) == 1:
        return hits.pop()
    return raw


def mentions_skill(text: str, skill: str) -> bool:
    """True if ``text`` mentions ``skill`` (canonical or free-text)."""
    pats = _patterns().get(skill)
    if pats:
        return any(p.search(text) for p in pats)
    return re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", text, re.IGNORECASE) is not None
