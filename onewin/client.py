import json
import re
from time import time as current_time, sleep
from random import uniform
import cloudscraper
from bots.base.base import BaseFarmer
from telethon.types import InputBotAppShortName
from bots.onewin.strings import (
    HEADERS, BUILDING_INFO,
    URL_INIT, URL_ACCOUNT_BALANCE, URL_DAILY_REWARD_INFO, URL_MINING,
    URL_FRIENDS_INFO, URL_FRIEND_CLAIM,
    MSG_CURRENT_BALANCE, MSG_DAILY_REWARD, MSG_DAILY_REWARD_IS_COLLECTED,
    MSG_BUY_UPGRADE, MSG_BUY_BUILDING, MSG_ACCESS_TOKEN_ERROR, MSG_URL_ERROR,
    MSG_AUTHENTICATION_ERROR, MSG_ACCOUNT_INFO_ERROR, MSG_DAILY_REWARD_ERROR,
    MSG_INITIALIZATION_ERROR, MSG_FRIENDS_REWARD, MSG_FRIENDS_REWARD_ERROR,
    MSG_CLOUDFLARE_ERROR
)
from bots.onewin.config import (
    FEATURES, UPGRADE_MAX_LEVEL
)

def sorted_by_payback(upgrades):
    return sorted(upgrades, key=lambda x: x['cost'] / x['profit'])

class BotFarmer(BaseFarmer):
    name = "token1win_bot"
    auth_data = None
    extra_code = "refId5115285864"
    friends_coins = 0
    friends = 0
    upgrades = []
    daily_reward_is_collected = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = HEADERS.copy()  # Инициализация заголовков

    @property
    def initialization_data(self):
        return {
            "peer": self.name,
            "app": InputBotAppShortName(self.initiator.get_input_entity(self.name), "start"),
            "start_param": self.extra_code,
        }

    def authenticate(self):
        if not self.auth_data:
            try:
                init_data = self.initiator.get_auth_data(**self.initialization_data)
                self.auth_data = init_data
            except Exception as e:
                self.log(MSG_INITIALIZATION_ERROR.format(error=e))

        try:
            self.headers['x-user-id'] = str(self.auth_data['userId'])
            self.scraper = cloudscraper.create_scraper()  # Инициализация скрапера
            response = self.scraper.post(URL_INIT, headers=self.headers, params=self.auth_data['authData'])

            if response.status_code == 200:
                result = response.json()
                if token := result.get("token"):
                    self.headers["Authorization"] = f"Bearer {token}"
                else:
                    self.error(MSG_ACCESS_TOKEN_ERROR)
            elif response.status_code == 403 and "Attention Required" in response.text:
                self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
            else:
                self.error(MSG_AUTHENTICATION_ERROR.format(status_code=response.status_code, text=response.text))
        except Exception as e:
            self.error(MSG_URL_ERROR.format(error=str(e)))

    def get_info(self):
        try:
            response = self.scraper.get(URL_ACCOUNT_BALANCE, headers=self.headers)
            if response.status_code == 200:
                result = response.json()
                self.balance = result.get("coinsBalance", 0)
                self.log(MSG_CURRENT_BALANCE.format(coins=self.balance))
            elif response.status_code == 403 and "Attention Required" in response.text:
                self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
            else:
                self.error(MSG_ACCOUNT_INFO_ERROR.format(status_code=response.status_code, text=response.text))
        except Exception as e:
            self.error(MSG_URL_ERROR.format(error=str(e)))

    def daily_reward_info(self):
        try:
            response = self.scraper.get(URL_DAILY_REWARD_INFO, headers=self.headers)
            if response.status_code == 200:
                result = response.json()
                if "days" in result and len(result["days"]) > 0:
                    self.daily_reward_is_collected = result["days"][0]["isCollected"]
                else:
                    self.error(MSG_DAILY_REWARD_ERROR.format(status_code=response.status_code, text="No 'days' in response"))
            elif response.status_code == 403 and "Attention Required" in response.text:
                self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
        except Exception as e:
            self.error(MSG_URL_ERROR.format(error=str(e)))

    def get_daily_reward(self):
        self.daily_reward_info()
        if self.daily_reward_is_collected is None:
            return

        if not self.daily_reward_is_collected:
            try:
                response = self.scraper.post(URL_DAILY_REWARD_INFO, headers=self.headers)
                if response.status_code == 200:
                    result = response.json()
                    self.daily_reward = result["days"][0]["money"]
                    self.log(MSG_DAILY_REWARD.format(coins=self.daily_reward))
                elif response.status_code == 403 and "Attention Required" in response.text:
                    self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
                else:
                    self.error(MSG_DAILY_REWARD_ERROR.format(status_code=response.status_code, text=response.text))
            except Exception as e:
                self.error(MSG_URL_ERROR.format(error=str(e)))
        else:
            self.log(MSG_DAILY_REWARD_IS_COLLECTED)

    def friends_info(self):
        try:
            response = self.scraper.get(URL_FRIENDS_INFO, headers=self.headers)
            if response.status_code == 200:
                result = response.json()
                self.friends = result.get("total_friends", 0)
                self.friends_coins = result.get("total_coins", 0)
            elif response.status_code == 403 and "Attention Required" in response.text:
                self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
        except Exception as e:
            self.error(MSG_URL_ERROR.format(error=str(e)))

    def friends_claim(self):
        self.friends_info()
        if self.friends_coins > 0:
            try:
                response = self.scraper.post(URL_FRIEND_CLAIM, headers=self.headers)
                if response.status_code == 200:
                    result = response.json()
                    coins_collected = result.get("coinsCollected", 0)
                    self.log(MSG_FRIENDS_REWARD.format(coins=coins_collected))
                elif response.status_code == 403 and "Attention Required" in response.text:
                    self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
                else:
                    self.error(MSG_FRIENDS_REWARD_ERROR.format(status_code=response.status_code, text=response.text))
            except Exception as e:
                self.error(MSG_URL_ERROR.format(error=str(e)))

    def upgrades_list(self):
        try:
            response = self.scraper.get(URL_MINING, headers=self.headers)
            if response.status_code == 200:
                self.upgrades = response.json()
            elif response.status_code == 403 and "Attention Required" in response.text:
                self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
        except Exception as e:
            self.error(MSG_URL_ERROR.format(error=str(e)))

    def get_sorted_upgrades(self, sort_method):
        methods = dict(payback=sorted_by_payback)
        prepared = []
        self.upgrades_list()
        for upgrade in self.upgrades:
            if (
                upgrade["profit"] > 0
                and upgrade["level"] < UPGRADE_MAX_LEVEL
                and upgrade["cost"] <= FEATURES["max_upgrade_cost"]
                and upgrade["cost"] / upgrade["profit"] <= FEATURES["max_upgrade_payback"]
            ):
                upgrade["payback"] = round(upgrade["cost"] / upgrade["profit"], 2)
                prepared.append(upgrade.copy())
        
        return methods.get(sort_method)(prepared) if prepared else []

    def buy_upgrades(self):
        if not FEATURES["buy_upgrades"]:
            return

        counter = 0
        num_purchases_per_cycle = FEATURES["num_purchases_per_cycle"]
        while counter < num_purchases_per_cycle:
            sorted_upgrades = self.get_sorted_upgrades(FEATURES["buy_decision_method"])
            if sorted_upgrades:
                upgrade = sorted_upgrades[0]
                if (upgrade["cost"] * 2 <= self.balance) and (self.balance > FEATURES["min_cash_value_in_balance"]):
                    self.upgrade(upgrade['id'])
                    counter += 1
                    sleep(2 + uniform(0, 3))
                else:
                    break
            else:
                break

    def upgrade(self, upgrade_id, new_building=False):
        data = {"id": upgrade_id}
        english_name = re.sub(r'\d+', '', upgrade_id).lower()
        russian_name = BUILDING_INFO.get(english_name)["rus_name"]
        
        if not new_building:
            match = re.search(r'\d+', data['id'])
            if match:
                current_level = int(match.group())
                upgrade_level = current_level + 1
                new_id = data['id'].replace(str(current_level), str(upgrade_level))
                data['id'] = new_id
                try:
                    response = self.scraper.post(URL_MINING, json=data)
                    if response.status_code == 200:
                        self.log(MSG_BUY_UPGRADE.format(name=russian_name, level=upgrade_level))
                    elif response.status_code == 403 and "Attention Required" in response.text:
                        self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
                except Exception as e:
                    self.error(MSG_URL_ERROR.format(error=str(e)))
        else:
            try:
                response = self.scraper.post(URL_MINING, json=data)
                if response.status_code == 200:
                    self.log(MSG_BUY_BUILDING.format(name=russian_name))
                elif response.status_code == 403 and "Attention Required" in response.text:
                    self.error(MSG_CLOUDFLARE_ERROR.format(status_code=response.status_code, text=response.text))
            except Exception as e:
                self.error(MSG_URL_ERROR.format(error=str(e)))

        self.get_info()

    def buy_new_buildings(self):
        my_buildings = {re.sub(r'\d+', '', upgrade["id"]).lower(): upgrade["level"] for upgrade in self.upgrades}
        new_buildings = list(BUILDING_INFO.keys())
        self.get_info()
        
        for item in new_buildings:
            if item not in my_buildings:
                requirements = BUILDING_INFO[item]["requirements"]
                if (requirements is None) or (requirements["level"] <= my_buildings.get(requirements["name"], 0)):
                    if BUILDING_INFO[item]["min_balance"] <= self.balance:
                        self.upgrade(BUILDING_INFO[item]["purchase_id"], new_building=True)

    def set_start_time(self):
        self.start_time = current_time() + uniform(FEATURES["minimum_delay"], FEATURES["maximum_delay"])

    def farm(self):
        self.authenticate()
        self.get_info()  
        if FEATURES['get_daily_reward']:
            self.get_daily_reward()
        if FEATURES['friends_claim']:
            self.friends_claim()
        self.upgrades_list()
        if FEATURES['blind_upgrade']:
            self.buy_new_buildings()
        self.buy_upgrades()
