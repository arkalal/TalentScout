# Scenario 2: Natural Language Query Compare And Why

_Natural-language search, side-by-side comparison and a 'why did X rank higher than Y' explanation._

## Turn 1

**👤 Recruiter:** Find me candidates with React and 3+ years experience

<details><summary>🧠 Agent reasoning trace (graph nodes)</summary>

- `parse_jd` — Parsed input as search_query: React Developer (mid)
- `extract_requirements` — Must-have: React (3+y). Nice-to-have: —. Min total experience: 3y.
- `search_resumes` — RAG-scored all 100 resumes (762 chunks). Must-have coverage: React 37
- `round1_screen` — Round 1: scored 100 resumes → top 10 (cut-off 97.9); 61 miss ≥1 must-have
- `round2_deep_analysis` — Round 2: LLM deep review of 10 resumes; re-ranked by 40% R1 + 60% deep fit
- `round3_final_decision` — Round 3: 6 hire · 4 borderline · 0 no-hire
- `generate_report` — Match report generated (0 ranking changes)

</details>

**🎯 TalentScout:**

## 🎯 React Developer — shortlist

**Requirements (v1):** Must-have: React (3+y). Nice-to-have: —. Min total experience: 3y.

**Funnel:** Round 1 screened **100** resumes → top **10** (cut-off score 97.9) → Round 2 deep review of 10 → Round 3: 6 hire · 4 borderline · 0 no-hire

| # | Candidate | Final | R1 | Deep fit | Exp | Must-haves met | Recommendation |
|---|---|---|---|---|---|---|---|
| 1 | Swati Haddad (C024) | **93.9** | 99.7 | 90 | 11.5y | 1/1 | 🟢 HIRE |
| 2 | Gita Patel (C066) | **92.8** | 100.0 | 88 | 8.9y | 1/1 | 🟢 HIRE |
| 3 | Omkar Rossi (C062) | **92.6** | 99.5 | 88 | 8.4y | 1/1 | 🟢 HIRE |
| 4 | John Carter (C017) | **92.6** | 99.5 | 88 | 8.4y | 1/1 | 🟢 HIRE |
| 5 | Noah Rossi (C048) | **90.7** | 99.2 | 85 | 3.2y | 1/1 | 🟡 BORDERLINE |
| 6 | Diego Andersen (C008) | **90.6** | 98.9 | 85 | 7.1y | 1/1 | 🟡 BORDERLINE |
| 7 | Omar Pillai (C003) | **90.5** | 98.7 | 85 | 4.6y | 1/1 | 🟡 BORDERLINE |
| 8 | Maria Reddy (C018) | **90.3** | 98.3 | 85 | 5.1y | 1/1 | 🟢 HIRE |
| 9 | Bhavna Petrov (C060) | **90.2** | 97.9 | 85 | 5.5y | 1/1 | 🟡 BORDERLINE |
| 10 | Dana Gupta (C077) | **90.2** | 97.9 | 85 | 7.4y | 1/1 | 🟢 HIRE |

**Summary:** The shortlist includes several strong candidates with extensive React experience and leadership, notably Swati Haddad, Gita Patel, John Carter, Maria Reddy, and Dana Gupta, who are clear hires. Candidates like Omkar Rossi, Noah Rossi, Diego Andersen, Omar Pillai, and Bhavna Petrov show solid skills but have some gaps or risks such as leadership experience, resume inconsistencies, or ecosystem tool familiarity, placing them borderline. The committee should focus interviews on clarifying these gaps and verifying leadership and technical depth for borderline candidates.

**1. Swati Haddad** — 🟢 HIRE · ✔ Extensive React and React Native experience exceeding 11 years; Proven impact on app performance and release efficiency · ✖ none significant

**2. Gita Patel** — 🟢 HIRE · ✔ Extensive React experience exceeding 3 years with demonstrated impact on performance and scalability; End-to-end ownership of full stack features involving React in senior roles · ✖ none significant

**3. Omkar Rossi** — 🟢 HIRE · ✔ Extensive React experience well beyond 3 years minimum requirement; Demonstrated leadership and mentoring skills · ✖ No explicit mention of React-specific testing frameworks or state management libraries (e.g., Redux); No direct mention of front-end architecture or UI/UX design contributions beyond data modeling

📄 Full match report saved to `reports/react_developer_v1_20261031_151346.md`.

_Try: “Compare the top 3 side by side” · “Why did #1 rank higher than #2?” · “Make AWS a must-have” · “Interview questions for #1”_

_⏱ 20.0s_

## Turn 2

**👤 Recruiter:** Compare the top 3 matches side by side

<details><summary>🧠 Agent reasoning trace (graph nodes)</summary>

- `understand_request` — Intent: compare — The user explicitly requests a side-by-side comparison of the top 3 candidates.
- `compare_candidates` — Compared C024, C066, C062

</details>

**🎯 TalentScout:**

### Head-to-head: Swati Haddad vs Gita Patel vs Omkar Rossi

| | **Swati Haddad** (C024) | **Gita Patel** (C066) | **Omkar Rossi** (C062) |
|---|---|---|---|
| Final rank / score | #1 · 93.9 | #2 · 92.8 | #3 · 92.6 |
| Recommendation | HIRE | HIRE | HIRE |
| Round 1 score | 99.7 | 100.0 | 99.5 |
| Deep-review fit | 90 | 88 | 88 |
| Total experience | 11.5y | 8.9y | 8.4y |
| Must: React (3+y) | ✅ 11.8y | ✅ 9.2y | ✅ 8.6y |
| Top strength | Extensive React and React Native experience exceeding 11 years. | Extensive React experience exceeding 3 years with demonstrated impact on performance and scalability. | Extensive React experience well beyond 3 years minimum requirement. |
| Main gap | — | — | No explicit mention of React-specific testing frameworks or state management libraries (e.g., Redux). |

Swati Haddad is the strongest fit for this React Developer role due to their exceptional 11.8 years of React experience, proven leadership in performance optimization, and delivery of high-profile mobile applications with millions of users. Their seniority and deep expertise exceed the role’s requirements, ensuring immediate high impact. Gita Patel and Omkar Rossi are also strong candidates but have slightly less React experience and fewer demonstrated leadership or specialized React contributions.

Choose Swati Haddad if you want a highly experienced React developer with proven leadership and impact on large-scale, high-traffic applications.  
Choose Gita Patel if you want a senior full stack engineer with strong React expertise and end-to-end ownership of scalable features.  
Choose Omkar Rossi if you want a senior full stack engineer with solid React experience and leadership but less emphasis on React-specific frameworks or UI architecture.

_⏱ 3.6s_

## Turn 3

**👤 Recruiter:** Why did John rank higher than Jane?

<details><summary>🧠 Agent reasoning trace (graph nodes)</summary>

- `understand_request` — Intent: explain_ranking — The user is asking for a comparison explanation between two specific candidates regarding their ranking.
- `explain_ranking` — Explained ranking for C017, C042

</details>

**🎯 TalentScout:**

| Round-1 component (weighted pts) | John Carter | Jane Fernandes | Δ |
|---|---|---|---|
| semantic relevance | 19.5 | 16.9 | +2.6 |
| must-have coverage | 45.0 | 45.0 | +0.0 |
| nice-to-have coverage | 15.0 | 15.0 | +0.0 |
| experience fit | 20.0 | 20.0 | +0.0 |
| **Round-1 total** | **99.5** | **96.9** | **+2.6** |

John ranked higher than Jane primarily due to a stronger semantic relevance score in Round 1, which reflects how well their resume and experience matched the role beyond just listed skills.

- Both John and Jane fully met the must-have React requirement (3+ years), scoring the maximum 45.0 points there.
- They also both scored perfectly on nice-to-have (15.0) and experience fit (20.0), reflecting sufficient total experience (John 8.4 years, Jane 5.2 years).
- The key difference was semantic relevance: John scored 19.5/20, while Jane scored 16.9/20, a 2.6-point advantage. This suggests John's resume better highlighted relevant React leadership, testing, performance optimization, and collaboration skills.
- John's Round 1 total was 99.5 versus Jane's 96.9, exceeding the shortlist cut-off of 97.9, so John advanced to Round 2 deep review while Jane did not.
- In deep review, John scored 88/100 on fit, reinforcing their strong alignment with the role.

In summary, John’s richer, more detailed evidence of React expertise and impact gave them a clear edge in semantic relevance, pushing their overall Round 1 score above the cut-off and securing a higher final ranking. Jane’s gap was meaningful enough that they did not reach Round 2.

_⏱ 4.1s_
