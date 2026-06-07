import logging


def pytest_configure(config):
    logging.getLogger("agent_platform").setLevel(logging.WARNING)