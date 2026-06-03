from operator_day.connectors.catalog import operation_catalog
from operator_day.connectors.safety import OperationSafety


def test_operation_catalog_contains_ozon_catalog_and_ads_workflows() -> None:
    catalog = operation_catalog()

    product_list = catalog["ProductAPI_GetProductList"]
    campaigns = catalog["ListCampaigns"]

    assert product_list.platform == "ozon"
    assert product_list.safety == OperationSafety.READ
    assert product_list.rate_limit_key == "ozon:seller:ProductAPI_GetProductList"
    assert campaigns.platform == "ozon_performance"
    assert campaigns.safety == OperationSafety.READ
    assert campaigns.rate_limit_key == "ozon:performance:ListCampaigns"


def test_operation_catalog_marks_live_write_as_confirmed_action() -> None:
    catalog = operation_catalog()

    assert catalog["ReviewAPI_SendAnswer"].safety == OperationSafety.WRITE
    assert catalog["Campaign_Stop"].safety == OperationSafety.WRITE


def test_operation_catalog_contains_wb_and_yandex_core_operations() -> None:
    catalog = operation_catalog()

    assert catalog["WB_Content_GetCardsList"].platform == "wb"
    assert catalog["WB_Questions_PatchAnswer"].safety == OperationSafety.WRITE
    assert catalog["YM_GetBidsInfoForBusiness"].platform == "yandex_market"
    assert catalog["YM_UpdateCampaignBids"].safety == OperationSafety.WRITE
