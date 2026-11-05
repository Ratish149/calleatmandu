from order.models import OrderConfig


class OrderConfigService:
    @staticmethod
    def get_config() -> OrderConfig:
        """
        Retrieves the singleton OrderConfig instance.
        """
        return OrderConfig.get_instance()

    @staticmethod
    def toggle_take_order() -> OrderConfig:
        """
        Toggles the take_order boolean status on the singleton OrderConfig.
        """
        config = OrderConfig.get_instance()
        config.take_order = not config.take_order
        config.save()
        return config

    @staticmethod
    def update_config(*, take_order: bool) -> OrderConfig:
        """
        Explicitly sets the take_order boolean status on the singleton OrderConfig.
        """
        config = OrderConfig.get_instance()
        config.take_order = take_order
        config.save()
        return config
