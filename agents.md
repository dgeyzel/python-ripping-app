# Instructions to Cursor

## Tooling

- Use uv for Python package management
- Place tests in the "tests" directory
- Place the application code in the "src" directory

## Security

- Do NOT commit .env file
- Use load_dotenv() from dotenv for all secrets
- Never log passwords or tokens

## Format

- Follow PEP 8 style guidelines and prefer f-strings for formatting
- Line length is a maximum of 88 characters
- Handle errors with specific exception types, avoid bare except clauses
- Include docstrings for public functions using Google style format
- Prefer pathlib over os.path and use context managers for resources

## Testing preferences

- Write all Python tests as `pytest` style functions, not unittest classes
- Use descriptive function names starting with `test_`
- Prefer fixtures over setup/teardown methods
- Use assert statements directly, not self.assertEqual

## Testing approach

- Never create throwaway test scripts or ad hoc verification files
- If you need to test functionality, write a proper test in the test suite
- All tests go in the `tests/` directory following the project structure
- Tests should be runnable with the rest of the suite (`run pytest`)
- Even for quick verification, write it as a real test that provides ongoing value
- Make sure that all tests are passing after making a change
- If a problem is found, add a regression test to the test suite to prevent the problem from happening again
