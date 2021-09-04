from .config.config import HarvestConfig
from .service_dynamo.dynamo import ServiceDynamo
from .service_kucoin.account import Account
from .service_ses.ses import ServiceSES
from .service_sns.sns import ServiceSNS

HC = HarvestConfig()
DYNAMO = ServiceDynamo()
SES = ServiceSES()
SNS = ServiceSNS()

ACCOUNT = Account(
    dynamo=DYNAMO, tablename=HC.table_account,
    key=HC.kucoin_key, secret=HC.kucoin_secret, api_pass_phrase=HC.kucoin_api_passphrase,
    max_trades=HC.strategy_max_trades,
    name="TRADE"
)
ACCOUNT.init_account()
