import json
import time
from typing import Any

import requests
from bulk_sync import bulk_sync
from cardpicker.models import DFCPair
from cardpicker.utils.to_searchable import to_searchable
from django.core.management.base import BaseCommand


def sync_dfcs() -> None:
    t0 = time.time()
    print("Querying Scryfall for DFC pairs...")
    scryfall_query_dfc = (
        "https://api.scryfall.com/cards/search?q=is:dfc%20-layout:art_series%20-layout:double_faced_token"
    )
    response_dfc = json.loads(requests.get(scryfall_query_dfc).content)

    data = response_dfc["data"]
    while response_dfc["has_more"]:
        response_dfc = json.loads(requests.get(response_dfc["next_page"]).content)
        data += response_dfc["data"]

    # maintain list of all dfcs found so far
    q_dfcpairs = []

    for x in data:
        # retrieve front and back names for this card, then create a DFCPair for it and append to list
        front_name = x["card_faces"][0]["name"]
        back_name = x["card_faces"][1]["name"]
        q_dfcpairs.append(
            DFCPair(
                front=front_name,
                front_searchable=to_searchable(front_name),
                back=back_name,
                back_searchable=to_searchable(back_name),
            )
        )

    # also retrieve meld pairs and save them as DFCPairs
    time.sleep(0.1)
    scryfall_query_meld = "https://api.scryfall.com/cards/search?q=is:meld%"
    response_meld = json.loads(requests.get(scryfall_query_meld).content)

    for x in response_meld["data"]:
        card_part = [y for y in x["all_parts"] if y["name"] == x["name"]][0]
        meld_result = [y for y in x["all_parts"] if y["component"] == "meld_result"][0]["name"]
        if card_part["component"] == "meld_part":
            is_top = "\n(Melds with " not in x["oracle_text"]
            card_bit = "Top" if is_top else "Bottom"
            q_dfcpairs.append(
                DFCPair(
                    front=x["name"],
                    front_searchable=to_searchable(x["name"]),
                    back=f"{meld_result} ({card_bit})",
                    back_searchable=to_searchable(f"{meld_result} {card_bit}"),
                )
            )

    # synchronise the located DFCPairs to database
    key_fields = ("front",)
    ret = bulk_sync(new_models=q_dfcpairs, key_fields=key_fields, filters=None, db_class=DFCPair)

    print("Finished synchronising database with Scryfall DFCs, which took {} seconds.".format(time.time() - t0))


class Command(BaseCommand):
    # set up help line to print the available drive options
    help = "Synchronises stored double-faced card pairs with Scryfall database."

    def handle(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        sync_dfcs()
