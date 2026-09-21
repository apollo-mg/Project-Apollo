# intentionally empty: isolates the fixture to ONLY the injected google-workspace
# skill. Without this, upstream bundled skills compete -- observed the agent reaching for
# 'himalaya envelope list' (skills/email/himalaya) instead of the fake-google skill, which
# confounds tool CHOICE with tool USE. Skill-selection-under-competition is a separate
# scenario class, not a default.
