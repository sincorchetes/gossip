import logging


class SuppressDuplicatePrimaryURLFilter(logging.Filter):
    """Silences mkdocstrings-autorefs 'Multiple primary URLs found' warnings.

    These warnings occur in multilingual (i18n) builds because identical Python
    symbols are documented in both default ('en') and translated ('es') trees.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "Multiple primary URLs found" not in record.getMessage()


def _attach_filter():
    filter_obj = SuppressDuplicatePrimaryURLFilter()
    for name in ["mkdocs.plugins.mkdocs_autorefs", "mkdocs_autorefs", "autorefs"]:
        logger = logging.getLogger(name)
        if not any(isinstance(f, SuppressDuplicatePrimaryURLFilter) for f in logger.filters):
            logger.addFilter(filter_obj)

    for name, logger in logging.Logger.manager.loggerDict.items():
        if "autorefs" in name and isinstance(logger, logging.Logger):
            if not any(isinstance(f, SuppressDuplicatePrimaryURLFilter) for f in logger.filters):
                logger.addFilter(filter_obj)


def on_config(config, **kwargs):
    _attach_filter()
    return config


def on_pre_build(config, **kwargs):
    _attach_filter()
    return config
