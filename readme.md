### install all dependencies

uv pip install -r pyproject.toml --all-extras

uv run fastapi dev

no sql (mongodb)
User schema

- api key
- auth_id
- email
- notification
- unit_dashboard_preference: []

Unit_dashboard

- dashboard_id
- unit_id
- total questions
- open questions
- resolved
- flagged
- members: User [] { access_level}
- ed_form_link

Question_Cluster

- id
  -unit_id
- summarized topic
- answer
- has_answered
- related quetsion [{questions_id, text }]

FAQs

- id
- questions clusters:[]
- unit_id
- week
- generated_date

Backend Services

- Celery
- Redis
- flower (https://github.com/mher/flower)
- mongodb
- MongoDB Motor
- MongoDB ODMantic
