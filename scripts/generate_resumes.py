"""Generate 100 realistic, varied synthetic resumes (deterministic, seed 42).

Resumes are written as Markdown to data/resumes/<ID>_<name>.md. Skill mixes, seniority
and career histories are controlled so that rankings are meaningful in the demo:
there are strong, borderline and weak matches for each of the sample JDs.

    python scripts/generate_resumes.py
"""

from __future__ import annotations

import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "resumes"
NOW_YEAR, NOW_MONTH = 2026, 10
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

FIRST_NAMES = [
    "Aarav", "Aditi", "Akash", "Ananya", "Arjun", "Bhavna", "Chirag", "Deepika", "Dev", "Divya",
    "Farhan", "Gauri", "Harsh", "Ishita", "Jatin", "Kavya", "Karan", "Lakshmi", "Manish", "Meera",
    "Nikhil", "Neha", "Omkar", "Pooja", "Pranav", "Priya", "Rahul", "Riya", "Rohan", "Sanya",
    "Sameer", "Shreya", "Siddharth", "Sneha", "Tanvi", "Tarun", "Uday", "Varun", "Vidya", "Yash",
    "Zoya", "Aisha", "Kabir", "Nisha", "Vikram", "Anjali", "Rakesh", "Swati", "Kunal", "Pallavi",
    "Alex", "Maria", "Daniel", "Sofia", "Ethan", "Olivia", "Lucas", "Emma", "Noah", "Chloe",
    "Liam", "Grace", "Mateo", "Hannah", "Omar", "Leila", "Kenji", "Mei", "Lars", "Ingrid",
    "Diego", "Camila", "Tomas", "Elena", "Samuel", "Fatima", "Ravi", "Asha", "Irfan", "Naina",
    "Gaurav", "Hema", "Mohit", "Ritika", "Sahil", "Trisha", "Abhinav", "Bianca", "Carlos", "Dana",
    "Felix", "Gita", "Hugo", "Isla", "Joel", "Kiara", "Leo", "Mira", "Nora", "Oscar",
]
LAST_NAMES = [
    "Sharma", "Iyer", "Reddy", "Nair", "Gupta", "Menon", "Patel", "Rao", "Kulkarni", "Banerjee",
    "Chatterjee", "Joshi", "Mehta", "Kapoor", "Singh", "Das", "Pillai", "Bose", "Verma", "Malhotra",
    "Khan", "Fernandes", "D'Souza", "Thomas", "Mathew", "Garcia", "Kim", "Nguyen", "Silva", "Müller",
    "Rossi", "Tanaka", "Andersen", "Lopez", "Cohen", "Haddad", "Okafor", "Novak", "Petrov", "Wong",
]
LOCATIONS = ["Bengaluru, India", "Hyderabad, India", "Pune, India", "Mumbai, India", "Delhi NCR, India",
             "Chennai, India", "Kolkata, India", "Remote (India)", "Singapore", "Berlin, Germany",
             "London, UK", "Toronto, Canada", "Austin, USA", "Amsterdam, Netherlands"]
COMPANIES = ["Flipkart", "Swiggy", "Razorpay", "Zoho", "Freshworks", "Infosys", "TCS", "Wipro", "Accenture",
             "Thoughtworks", "Atlassian", "Microsoft", "Amazon", "Google", "Adobe", "Intuit", "PhonePe",
             "Paytm", "Meesho", "CRED", "Zomato", "Ola", "Postman", "BrowserStack", "Chargebee",
             "InMobi", "Myntra", "Groww", "Zerodha", "Dunzo", "Nykaa", "ShareChat", "Urban Company",
             "Byju's", "upGrad", "Capgemini", "Deloitte", "SAP Labs", "Oracle", "Walmart Global Tech",
             "Northwind Analytics", "BrightPath Labs", "Kite Systems", "Nimbus Cloud", "Quantive AI",
             "Pixelcraft Studio", "Ledgerly", "MediTrack Health", "ShopSphere", "Voyage Mobility"]
COLLEGES = ["IIT Bombay", "IIT Madras", "IIT Delhi", "NIT Trichy", "NIT Surathkal", "BITS Pilani", "IIIT Hyderabad",
            "VIT Vellore", "Manipal Institute of Technology", "PES University", "Anna University",
            "Jadavpur University", "Pune Institute of Computer Technology", "Delhi Technological University",
            "University of Toronto", "TU Munich", "National University of Singapore", "University of Texas at Austin"]
DEGREES = ["B.Tech in Computer Science", "B.E. in Information Technology", "B.Tech in Electronics & Communication",
           "B.Sc. in Computer Science", "M.Tech in Computer Science", "MCA", "M.S. in Computer Science",
           "B.Tech in Mechanical Engineering"]

ARCHETYPES: dict[str, dict] = {
    "frontend": {
        "count": 20,
        "titles": ["Frontend Developer", "Frontend Engineer", "Senior Frontend Engineer", "Lead Frontend Engineer"],
        "core": ["React", "JavaScript", "HTML", "CSS"],
        "optional": ["TypeScript", "Next.js", "Redux", "Tailwind CSS", "Jest", "Cypress", "GraphQL", "Webpack",
                     "Vue.js", "Angular", "Node.js", "AWS", "Docker", "REST APIs", "Agile"],
        "domain": "building fast, accessible web interfaces",
        "bullets": [
            "Built a {f} in {a} and {b}, cutting page load time by {n}%.",
            "Migrated a legacy {f} to {a}, reducing bundle size by {n}% and improving Lighthouse scores to 95+.",
            "Designed a reusable component library with {a} and {b} adopted by {k} product teams.",
            "Implemented end-to-end and unit tests with {a}, raising coverage from 40% to {cov}%.",
            "Collaborated with designers to ship a {f} used by {k}M+ monthly users, built on {a}.",
            "Optimised rendering performance of the {f} with memoisation and code-splitting in {a} ({n}% faster TTI).",
        ],
        "features": ["checkout flow", "analytics dashboard", "design system", "customer onboarding portal",
                     "real-time chat widget", "admin console", "search experience", "marketing site"],
    },
    "fullstack": {
        "count": 16,
        "titles": ["Software Engineer", "Full Stack Developer", "Senior Full Stack Engineer", "Staff Engineer"],
        "core": ["React", "Node.js", "JavaScript", "REST APIs"],
        "optional": ["TypeScript", "Next.js", "Express", "PostgreSQL", "MongoDB", "Docker", "AWS", "GraphQL", "Redis",
                     "Python", "Django", "Jest", "CI/CD", "Microservices", "Agile", "Kubernetes"],
        "domain": "shipping end-to-end product features",
        "bullets": [
            "Owned a {f} end to end: {a} frontend, {b} services and {c} storage, serving {k}M requests/day.",
            "Built {a} APIs and integrated them with a {b} UI for a {f}, launching {n} days ahead of plan.",
            "Containerised services with {a} and set up {b}, cutting deployment time by {n}%.",
            "Reduced API latency by {n}% by introducing {a} caching and query optimisation in {b}.",
            "Mentored {k} junior engineers and led code reviews for the {f} team using {a}.",
            "Designed the data model in {a} for a {f} supporting {k}x traffic growth.",
        ],
        "features": ["payments platform", "booking system", "subscription billing module", "internal CRM",
                     "seller portal", "notification service", "learning platform", "inventory tool"],
    },
    "backend_java": {
        "count": 10,
        "titles": ["Java Developer", "Backend Engineer", "Senior Backend Engineer", "Principal Engineer"],
        "core": ["Java", "Spring Boot", "REST APIs", "SQL"],
        "optional": ["Microservices", "Kafka", "Docker", "Kubernetes", "AWS", "Redis", "MySQL", "PostgreSQL",
                     "JUnit", "System Design", "Jenkins", "Elasticsearch", "Agile"],
        "domain": "building reliable, high-throughput backend systems",
        "bullets": [
            "Developed {a} {b} services for a {f} processing {k}M transactions per day.",
            "Decomposed a monolith into {a} communicating over {b}, improving deploy frequency {k}x.",
            "Introduced {a} event streaming for a {f}, reducing end-to-end latency by {n}%.",
            "Wrote {a} test suites and contract tests, reducing production incidents by {n}%.",
            "Tuned {a} queries and indexes for a {f}, cutting p99 latency by {n}%.",
            "Led the system design of a {f} built on {a} and {b}.",
        ],
        "features": ["ledger service", "order management system", "fraud detection pipeline", "loan origination platform",
                     "pricing engine", "settlement service"],
    },
    "backend_python": {
        "count": 10,
        "titles": ["Python Developer", "Backend Engineer", "Senior Backend Engineer", "Engineering Lead"],
        "core": ["Python", "REST APIs", "PostgreSQL"],
        "optional": ["Django", "FastAPI", "Flask", "Redis", "Docker", "AWS", "Kafka", "Kubernetes", "Pytest",
                     "Microservices", "RabbitMQ", "GCP", "SQL", "System Design", "Linux"],
        "domain": "designing clean, scalable Python services",
        "bullets": [
            "Built {a} services in {b} powering a {f} with {k}M monthly active users.",
            "Designed asynchronous job processing with {a} and {b}, cutting batch times by {n}%.",
            "Migrated a {f} from {a} to {b}, improving throughput by {n}%.",
            "Implemented {a} test automation achieving {cov}% coverage on critical paths.",
            "Deployed services on {a} using {b}, reducing infrastructure cost by {n}%.",
            "Exposed {a} for partners integrating with the {f}.",
        ],
        "features": ["claims processing platform", "content API", "catalogue service", "KYC workflow",
                     "reporting backend", "logistics tracker"],
    },
    "backend_go": {
        "count": 4,
        "titles": ["Backend Engineer", "Software Engineer (Go)", "Senior Platform Engineer", "Staff Engineer"],
        "core": ["Go", "Microservices", "gRPC"],
        "optional": ["Kubernetes", "Docker", "PostgreSQL", "Kafka", "AWS", "GCP", "Redis", "Prometheus", "System Design",
                     "Linux"],
        "domain": "building low-latency distributed services",
        "bullets": [
            "Wrote high-performance {a} services exposed via {b} for a {f} handling {k}K RPS.",
            "Ran {a} workloads on {b} with autoscaling, achieving 99.9{m}% availability.",
            "Built observability for the {f} with {a} metrics, reducing MTTR by {n}%.",
            "Designed an event-driven {f} using {a} and {b}.",
        ],
        "features": ["rate limiter", "API gateway", "real-time bidding system", "geo-location service", "feature-flag platform"],
    },
    "devops": {
        "count": 8,
        "titles": ["DevOps Engineer", "Site Reliability Engineer", "Senior DevOps Engineer", "Platform Engineering Lead"],
        "core": ["AWS", "Docker", "Kubernetes", "CI/CD", "Linux"],
        "optional": ["Terraform", "Jenkins", "GitHub Actions", "Prometheus", "Grafana", "Ansible", "Python", "GCP",
                     "Azure", "Go"],
        "domain": "automating infrastructure and keeping production healthy",
        "bullets": [
            "Provisioned {f} infrastructure on {a} with {b} as code across {k} environments.",
            "Built {a} pipelines that cut release lead time from days to {k} hours.",
            "Migrated {k}0+ services to {a}, improving resource utilisation by {n}%.",
            "Set up monitoring with {a} and {b}, reducing alert noise by {n}%.",
            "Hardened {a} hosts and automated patching with {b}.",
        ],
        "features": ["multi-region", "data platform", "payments", "microservices", "ML serving"],
    },
    "data_eng": {
        "count": 8,
        "titles": ["Data Engineer", "Senior Data Engineer", "Analytics Engineer", "Lead Data Engineer"],
        "core": ["Python", "SQL", "Spark", "Airflow"],
        "optional": ["dbt", "Snowflake", "Kafka", "AWS", "Pandas", "GCP", "Docker", "Tableau", "Scala", "PostgreSQL"],
        "domain": "building trustworthy data pipelines",
        "bullets": [
            "Built {a} batch pipelines orchestrated with {b} that process {k}TB of {f} data daily.",
            "Modelled a {f} warehouse in {a} using {b}, cutting analyst query time by {n}%.",
            "Implemented streaming ingestion with {a} for {f} events at {k}K events/sec.",
            "Reduced pipeline failures by {n}% with data-quality checks in {a}.",
        ],
        "features": ["clickstream", "finance", "marketing attribution", "supply-chain", "customer 360"],
    },
    "data_science": {
        "count": 12,
        "titles": ["Data Scientist", "Machine Learning Engineer", "Senior Data Scientist", "ML Lead"],
        "core": ["Python", "Machine Learning", "Pandas", "Scikit-learn", "SQL"],
        "optional": ["PyTorch", "TensorFlow", "Deep Learning", "NLP", "LLMs", "LangChain", "Computer Vision",
                     "Statistics", "A/B Testing", "NumPy", "AWS", "Docker", "Spark", "Tableau", "FastAPI"],
        "domain": "turning data into production ML systems",
        "bullets": [
            "Trained a {f} model with {a} and {b}, improving precision by {n}%.",
            "Deployed {a} models as APIs with {b}, serving {k}M predictions per day.",
            "Designed {a} experiments that lifted conversion by {m}% for the {f} initiative.",
            "Built a retrieval-augmented assistant using {a} and {b} for {f} support queries.",
            "Engineered features with {a} on {k}00M-row datasets for a {f} model.",
        ],
        "features": ["churn prediction", "recommendation", "demand forecasting", "fraud scoring",
                     "document classification", "customer support"],
    },
    "mobile": {
        "count": 7,
        "titles": ["Mobile Developer", "Android Engineer", "iOS Engineer", "Senior Mobile Engineer"],
        "core": ["React Native", "JavaScript"],
        "optional": ["Flutter", "Dart", "Kotlin", "Android", "Swift", "iOS", "TypeScript", "Redux", "REST APIs",
                     "GraphQL", "Jest", "CI/CD", "React"],
        "domain": "crafting smooth mobile experiences",
        "bullets": [
            "Shipped a {f} app in {a} with {k}M+ downloads and a 4.{m} store rating.",
            "Cut app start-up time by {n}% by profiling and optimising {a} rendering.",
            "Integrated {a} with {b} backends and offline sync for the {f} app.",
            "Set up {a} for automated mobile releases, reducing release effort by {n}%.",
        ],
        "features": ["fitness", "food delivery", "banking", "ride-hailing", "e-commerce", "telemedicine"],
    },
    "qa": {
        "count": 5,
        "titles": ["QA Engineer", "SDET", "Senior QA Automation Engineer", "QA Lead"],
        "core": ["Selenium", "CI/CD"],
        "optional": ["Playwright", "Cypress", "Java", "Python", "JavaScript", "Pytest", "JUnit", "Appium",
                     "REST APIs", "Jenkins", "Agile"],
        "domain": "building automation that lets teams ship with confidence",
        "bullets": [
            "Built a {a} automation framework covering {k}00+ regression cases for the {f}.",
            "Integrated {a} suites into {b}, cutting regression time from 2 days to {k} hours.",
            "Introduced API contract tests with {a}, catching {n}% of defects before staging.",
            "Mentored {k} manual testers in {a} automation.",
        ],
        "features": ["payments app", "web storefront", "mobile banking app", "partner portal"],
    },
}

CERTS = {
    "AWS": "AWS Certified Solutions Architect – Associate",
    "Kubernetes": "Certified Kubernetes Administrator (CKA)",
    "GCP": "Google Cloud Professional Cloud Architect",
    "Azure": "Microsoft Certified: Azure Developer Associate",
    "Terraform": "HashiCorp Certified: Terraform Associate",
    "Machine Learning": "DeepLearning.AI Machine Learning Specialization",
    "React": "Meta Front-End Developer Professional Certificate",
    "Java": "Oracle Certified Professional: Java SE Developer",
    "Snowflake": "SnowPro Core Certification",
    "Selenium": "ISTQB Certified Tester – Foundation Level",
}


@dataclass
class Role:
    title: str
    company: str
    start: tuple[int, int]  # (year, month 1-12)
    end: tuple[int, int] | None  # None = Present
    tech: list[str]
    bullets: list[str] = field(default_factory=list)


@dataclass
class Persona:
    cid: str
    name: str
    archetype: str
    years: float
    location: str
    skills: list[str]
    roles: list[Role]
    summary: str = ""
    education: str = ""
    certs: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)


def months_back(months: int) -> tuple[int, int]:
    total = NOW_YEAR * 12 + (NOW_MONTH - 1) - months
    return total // 12, total % 12 + 1


def fmt(ym: tuple[int, int] | None) -> str:
    return "Present" if ym is None else f"{MONTHS[ym[1] - 1]} {ym[0]}"


def seniority_title(titles: list[str], years_at_role: float) -> str:
    if years_at_role < 2.5:
        return titles[0] if random.random() < 0.6 else titles[1]
    if years_at_role < 5:
        return titles[1]
    if years_at_role < 9:
        return titles[2]
    return titles[3]


def fill(template: str, tech: list[str], features: list[str]) -> str:
    picks = random.sample(tech, k=min(3, len(tech))) + tech[:3]
    return template.format(a=picks[0], b=picks[1] if len(picks) > 1 else picks[0], c=picks[2] if len(picks) > 2 else picks[0],
                           f=random.choice(features), n=random.randint(18, 65), k=random.randint(2, 9),
                           m=random.randint(3, 9), cov=random.randint(72, 92))


def build_roles(arch: dict, years: float, skills: list[str], forced_tech: dict[int, list[str]] | None = None) -> list[Role]:
    total_months = max(6, int(round(years * 12)))
    n_roles = 1 if total_months < 24 else random.choice([2, 2, 3]) if total_months < 72 else random.choice([3, 3, 4])
    cuts = sorted(random.sample(range(6, total_months - 5), k=n_roles - 1)) if n_roles > 1 else []
    bounds = [0] + cuts + [total_months]  # months back from now; segment i: [bounds[i], bounds[i+1])
    companies = random.sample(COMPANIES, k=n_roles)
    roles: list[Role] = []
    for i in range(n_roles):
        end_back, start_back = bounds[i], bounds[i + 1]
        years_at_start = (total_months - start_back) / 12
        title = seniority_title(arch["titles"], years_at_start + (start_back - end_back) / 24)
        if forced_tech and i in forced_tech:
            tech = forced_tech[i]
        else:
            core = [s for s in arch["core"] if s in skills and random.random() < 0.85]
            extra = [s for s in skills if s not in arch["core"]]
            tech = core + random.sample(extra, k=min(len(extra), random.randint(2, 4)))
        role = Role(title=title, company=companies[i], start=months_back(start_back),
                    end=None if end_back == 0 else months_back(end_back), tech=tech)
        n_bullets = 3 if i == 0 else 2
        templates = random.sample(arch["bullets"], k=min(n_bullets, len(arch["bullets"])))
        role.bullets = [fill(t, tech, arch["features"]) for t in templates]
        roles.append(role)
    return roles


def random_persona(cid: str, name: str, archetype: str) -> Persona:
    arch = ARCHETYPES[archetype]
    years = round(random.choice([random.uniform(0.5, 3), random.uniform(2, 6), random.uniform(4, 9), random.uniform(7, 14)]), 1)
    core = [s for s in arch["core"] if random.random() < 0.9] or arch["core"][:1]
    optional = random.sample(arch["optional"], k=random.randint(3, min(8, len(arch["optional"]))))
    skills = list(dict.fromkeys(core + optional))
    roles = build_roles(arch, years, skills)
    used = {s for r in roles for s in r.tech}
    listed_only = [s for s in skills if s not in used]
    p = Persona(cid=cid, name=name, archetype=archetype, years=years, location=random.choice(LOCATIONS),
                skills=list(dict.fromkeys([s for r in roles for s in r.tech] + listed_only)), roles=roles)
    finalize(p, arch)
    return p


def finalize(p: Persona, arch: dict) -> None:
    top = ", ".join(p.skills[:4])
    yrs = f"{p.years:g}" if p.years >= 1 else "less than 1"
    p.summary = (f"{p.roles[0].title} with {yrs} year{'s' if p.years >= 1.5 else ''} of experience {arch['domain']}. "
                 f"Hands-on with {top}. " + random.choice([
                     "Enjoys mentoring and clear technical writing.",
                     "Comfortable owning features from design to production.",
                     "Strong collaborator across product, design and QA.",
                     "Focused on measurable impact and code quality.",
                     "Thrives in fast-moving startup environments.",
                 ]))
    grad_year = NOW_YEAR - int(p.years) - random.randint(0, 1)
    p.education = f"{random.choice(DEGREES)} — {random.choice(COLLEGES)} ({grad_year})"
    p.certs = [CERTS[s] for s in p.skills if s in CERTS and random.random() < 0.35]
    if random.random() < 0.7:
        s1, s2 = (p.skills + p.skills)[1], (p.skills + p.skills)[2]
        p.projects = [f"Open-source contributor: built a small {s1} + {s2} toolkit ({random.randint(40, 900)} GitHub stars)."
                      if random.random() < 0.5 else
                      f"Side project: {random.choice(arch['features'])} prototype using {s1} and {s2}."]


def planted_personas() -> dict[str, Persona]:
    """Hand-crafted candidates that make the demo questions meaningful."""
    fe = ARCHETYPES["frontend"]
    planted: dict[str, Persona] = {}

    # John: strong senior React/TypeScript engineer — should top a React JD
    john_roles = [
        Role("Senior Frontend Engineer", "Razorpay", (2022, 4), None,
             ["React", "TypeScript", "Next.js", "Redux", "Jest", "GraphQL", "AWS"],
             ["Led the rebuild of the merchant dashboard in React and TypeScript with Next.js, cutting page load time by 48%.",
              "Built a shared design system with React and Tailwind CSS adopted by 7 product teams.",
              "Introduced Jest and Cypress testing, raising coverage from 40% to 85%, and deployed on AWS CloudFront."]),
        Role("Frontend Engineer", "Swiggy", (2019, 7), (2022, 3),
             ["React", "JavaScript", "Redux", "Webpack", "Jest"],
             ["Shipped the React checkout flow used by 12M+ monthly users.",
              "Optimised Webpack bundles and Redux state, improving TTI by 35%."]),
        Role("Software Engineer", "Infosys", (2018, 6), (2019, 6),
             ["JavaScript", "HTML", "CSS", "Angular"],
             ["Built internal dashboards with Angular, HTML and CSS for banking clients."]),
    ]
    planted["john"] = Persona("C017", "John Carter", "frontend", 8.3, "Bengaluru, India",
                              ["React", "TypeScript", "Next.js", "Redux", "JavaScript", "Jest", "Cypress", "GraphQL",
                               "Tailwind CSS", "AWS", "Webpack", "HTML", "CSS", "Angular"], john_roles)

    # Jane: solid but less experienced React dev, no TypeScript / testing depth
    jane_roles = [
        Role("Frontend Developer", "Meesho", (2023, 2), None,
             ["React", "JavaScript", "CSS", "HTML"],
             ["Built responsive React product pages in JavaScript and CSS for 3M daily shoppers.",
              "Worked with designers to implement pixel-perfect UI components."]),
        Role("UI Developer", "Pixelcraft Studio", (2021, 9), (2023, 1),
             ["Vue.js", "JavaScript", "HTML", "CSS"],
             ["Developed marketing sites in Vue.js and improved accessibility to WCAG AA."]),
    ]
    planted["jane"] = Persona("C042", "Jane Fernandes", "frontend", 5.1, "Pune, India",
                              ["React", "JavaScript", "HTML", "CSS", "Vue.js", "Tailwind CSS"],
                              jane_roles)

    # Borderline: great TypeScript/Angular engineer with only ~1.5 yrs React
    meera_roles = [
        Role("Senior Frontend Engineer", "Adobe", (2025, 3), None,
             ["React", "TypeScript", "Jest", "GraphQL"],
             ["Migrated an Angular analytics console to React and TypeScript, reducing bundle size by 30%.",
              "Introduced Jest testing standards across the team."]),
        Role("Frontend Engineer", "SAP Labs", (2019, 1), (2025, 2),
             ["Angular", "TypeScript", "HTML", "CSS", "Webpack"],
             ["Built enterprise Angular apps used by 400+ customers.",
              "Led the migration from AngularJS to Angular with TypeScript."]),
    ]
    planted["meera"] = Persona("C063", "Meera Iyer", "frontend", 7.8, "Bengaluru, India",
                               ["TypeScript", "Angular", "React", "Jest", "GraphQL", "HTML", "CSS", "Webpack"], meera_roles)

    # Keyword stuffer: lists React but never used it in a role
    vikram_roles = [
        Role("Backend Engineer", "TCS", (2021, 5), None, ["Java", "Spring Boot", "MySQL", "REST APIs"],
             ["Built Spring Boot REST APIs for an insurance claims system.",
              "Maintained MySQL schemas and stored procedures."]),
    ]
    planted["vikram"] = Persona("C088", "Vikram Malhotra", "backend_java", 5.5, "Delhi NCR, India",
                                ["Java", "Spring Boot", "MySQL", "REST APIs", "React", "TypeScript", "AWS"], vikram_roles)
    for key in planted:
        random.seed(sum(map(ord, key)))  # stable extras per persona
        finalize(planted[key], ARCHETYPES[planted[key].archetype])
    planted["jane"].certs = []
    planted["john"].certs = [CERTS["React"], CERTS["AWS"]]
    return planted


def render(p: Persona) -> str:
    lines = [f"# {p.name}", f"**{p.roles[0].title}** | {p.location}",
             f"Email: {p.name.lower().replace(' ', '.').replace(chr(39), '')}@example.com | "
             f"Phone: {'+91-9' if 'India' in p.location else '+1-555-'}{random.randint(1000000, 9999999)} | LinkedIn: linkedin.com/in/{p.name.lower().replace(' ', '-')}",
             "", "## Summary", p.summary, "", "## Skills", ", ".join(p.skills), "", "## Experience"]
    for r in p.roles:
        lines += [f"### {r.title} — {r.company} ({fmt(r.start)} – {fmt(r.end)})", f"Tech: {', '.join(r.tech)}"]
        lines += [f"- {b}" for b in r.bullets]
        lines.append("")
    lines += ["## Education", p.education, ""]
    if p.certs:
        lines += ["## Certifications"] + [f"- {c}" for c in p.certs] + [""]
    if p.projects:
        lines += ["## Projects"] + [f"- {x}" for x in p.projects] + [""]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    random.seed(42)
    planted = planted_personas()
    random.seed(42)
    reserved_ids = {p.cid for p in planted.values()}
    reserved_first = {p.name.split()[0] for p in planted.values()}
    first_names = [n for n in FIRST_NAMES if n not in reserved_first]
    random.shuffle(first_names)

    slots = [a for a, spec in ARCHETYPES.items() for _ in range(spec["count"])]
    for p in planted.values():  # planted personas take an archetype slot
        slots.remove(p.archetype)
    random.shuffle(slots)

    ids = [f"C{i:03d}" for i in range(1, 101) if f"C{i:03d}" not in reserved_ids]
    personas = list(planted.values())
    for cid, archetype, first in zip(ids, slots, first_names):
        personas.append(random_persona(cid, f"{first} {random.choice(LAST_NAMES)}", archetype))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for p in sorted(personas, key=lambda x: x.cid):
        slug = p.name.lower().replace(" ", "_").replace("'", "")
        (OUT / f"{p.cid}_{slug}.md").write_text(render(p), encoding="utf-8")
    print(f"Wrote {len(personas)} resumes to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
