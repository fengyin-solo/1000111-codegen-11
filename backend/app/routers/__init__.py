"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import order as router_order
from app.routers import waybill as router_waybill
from app.routers import vehicle as router_vehicle
from app.routers import driver as router_driver
from app.routers import temperature as router_temperature
from app.routers import excursion as router_excursion
from app.routers import warehouse as router_warehouse
from app.routers import inbound as router_inbound
from app.routers import outbound as router_outbound
from app.routers import inventory as router_inventory
from app.routers import trace as router_trace
from app.routers import quality as router_quality
from app.routers import route as router_route
from app.routers import dispatch as router_dispatch
from app.routers import device as router_device
from app.routers import maint as router_maint
from app.routers import alarm as router_alarm
from app.routers import customer as router_customer
from app.routers import billing as router_billing
from app.routers import report as router_report
from app.routers import setting as router_setting

ROUTERS = [router_order, router_waybill, router_vehicle, router_driver, router_temperature, router_excursion, router_warehouse, router_inbound, router_outbound, router_inventory, router_trace, router_quality, router_route, router_dispatch, router_device, router_maint, router_alarm, router_customer, router_billing, router_report, router_setting]
