.PHONY: test dev status

test:
	python3 -m pytest tests/ -q

status:
	bin/claude-idle-compact status

dev:
	claude --plugin-dir $(CURDIR)
