"""Pre-built workflow templates surfaced in the UI's template library."""
from app.models import WorkflowTemplate

TEMPLATES: list[WorkflowTemplate] = [
    WorkflowTemplate(
        id="meeting-to-tasks",
        name="Meeting Notes → Tasks",
        description="Turn raw meeting notes into a Notion project page with action items, "
        "and notify the team on Microsoft Teams.",
        example_prompt=(
            "Take today's meeting notes and create a Notion project page, generate action "
            "items for each owner mentioned, and post a summary to Microsoft Teams."
        ),
        tools_used=["notion", "teams"],
    ),
    WorkflowTemplate(
        id="sprint-planning",
        name="Sprint Planning Kickoff",
        description="Create a Notion sprint plan page, back it up as a Google Doc, "
        "and announce the sprint goal in Teams.",
        example_prompt=(
            "Create a Notion page for Sprint 14 planning with the goals I list, save a copy "
            "as a Google Doc in the team folder, and post the sprint goal to Teams."
        ),
        tools_used=["notion", "google_drive", "teams"],
    ),
    WorkflowTemplate(
        id="incident-response",
        name="Incident Response Log",
        description="Stand up an incident page in Notion, log a timeline doc to Drive, "
        "and alert the on-call channel in Teams.",
        example_prompt=(
            "We have an incident: create a Notion incident page with severity and impact, "
            "save the timeline to Google Drive, and alert the on-call Teams channel immediately."
        ),
        tools_used=["notion", "google_drive", "teams"],
    ),
    WorkflowTemplate(
        id="requirements-to-notion",
        name="Requirements → Notion Tasks",
        description="Convert an unstructured requirements list into a structured Notion "
        "page with checklist items, notifying stakeholders when done.",
        example_prompt=(
            "Here are this sprint's requirements: [paste list]. Create a Notion page breaking "
            "them into action items, and post a completion summary to Teams."
        ),
        tools_used=["notion", "teams"],
    ),
    WorkflowTemplate(
        id="meeting-followup",
        name="Meeting Follow-up",
        description="Summarize a meeting into Notion, schedule a follow-up meeting on the calendar, "
        "and notify the team on Teams.",
        example_prompt=(
            "Here are today's meeting notes: [paste your notes]. Create a Notion page summarizing "
            "this meeting, schedule a 30-minute follow-up meeting for next Monday at 3pm with "
            "[attendee emails], and post a summary to Microsoft Teams."
        ),
        tools_used=["notion", "calendar", "teams"],
    ),
]


def get_template(template_id: str) -> WorkflowTemplate | None:
    return next((t for t in TEMPLATES if t.id == template_id), None)
