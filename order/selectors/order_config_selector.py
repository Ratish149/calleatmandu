from order.models import OrderConfig


def get_order_config() -> OrderConfig:
    """
    Returns the singleton OrderConfig instance.
    """
    return OrderConfig.get_instance()
