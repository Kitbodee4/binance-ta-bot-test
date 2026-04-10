# Test File for GitHub Flow Skill

This is a test file to demonstrate the GitHub Flow Enforcer skill in action.

## What this demonstrates

When a user indicates they want to make changes or commit work, the GitHub Flow Enforcer skill should:

1. Detect if they're on main/master branch
2. Guide them to create a feature branch if needed
3. Help with proper commit formatting
4. Assist with push and PR creation
5. Enforce the rule: never commit directly to main

## Expected Behavior

In this test scenario:
- We started on master branch
- We stashed changes to work clean
- We created a feature branch: feat/test-github-flow-skill
- Now we're adding this test file
- When we commit, the skill should help format the commit properly
- When we push, it should help create a PR

This demonstrates the skill working as intended.