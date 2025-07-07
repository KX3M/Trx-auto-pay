from flask import Flask, jsonify
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import PrivateKey, to_base58check_address
import os
import requests

app = Flask(__name__)

# TRON client with API key
TRONGRID_API_KEY = "a6cd9888-4efd-4339-8078-0997ddd35a18"
client = Tron(HTTPProvider(api_key=TRONGRID_API_KEY))

# Commission wallet (admin cut)
CUT_WALLET = "TVwXueNC13YUwTJnRvfK9An1cF39Q1af8Q"
CUT_PERCENT = 2  # % cut from each payment


@app.route("/")
def home():
    return jsonify({"msg": "TRX Auto Pay API is live!"})


@app.route("/wallet")
def generate_wallet():
    pk = PrivateKey.random()
    address = pk.public_key.to_base58check_address()
    return jsonify({
        "address": address,
        "private_key": pk.hex(),
        "tronscan": f"https://tronscan.org/#/address/{address}"
    })


@app.route("/balance/<address>")
def get_balance(address):
    try:
        balance = client.get_account_balance(address)
        return jsonify({"address": address, "balance": balance})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/pay/<private_key>/<to>/<amount>")
def send_trx(private_key, to, amount):
    try:
        sender = PrivateKey(bytes.fromhex(private_key))
        sender_address = sender.public_key.to_base58check_address()

        amount = float(amount)
        cut_amount = round((amount * CUT_PERCENT) / 100, 6)
        user_amount = round(amount - cut_amount, 6)

        # ✅ Transaction 1: Send to User
        user_txn = (
            client.trx.transfer(sender_address, to, user_amount)
            .build()
            .sign(sender)
        )
        user_receipt = user_txn.broadcast().wait()

        # ✅ Transaction 2: Admin Commission Transfer
        admin_txn = (
            client.trx.transfer(sender_address, CUT_WALLET, cut_amount)
            .build()
            .sign(sender)
        )
        admin_receipt = admin_txn.broadcast().wait()

        # ✅ Final Response
        return jsonify({
            "status": "success",
            "message": "Transfer completed successfully with admin cut.",
            "sender": sender_address,
            "transfers": {
                "user": {
                    "to": to,
                    "amount": user_amount,
                    "txid": user_txn.txid,
                    "tronscan": f"https://tronscan.org/#/transaction/{user_txn.txid}"
                },
                "admin_fee": {
                    "to": CUT_WALLET,
                    "amount": cut_amount,
                    "txid": admin_txn.txid,
                    "tronscan": f"https://tronscan.org/#/transaction/{admin_txn.txid}"
                }
            }
        })

    except Exception as e:
        return jsonify({
            "status": "failed",
            "error": str(e)
        }), 500

@app.route("/history/<address>")
def tx_history(address):
    try:
        url = f"https://api.trongrid.io/v1/accounts/{address}/transactions?limit=1"
        headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY}
        res = requests.get(url, headers=headers).json()

        latest = res.get("data", [{}])[0]
        value_data = latest.get("raw_data", {}).get("contract", [{}])[0].get("parameter", {}).get("value", {})

        owner_hex = value_data.get("owner_address")
        to_hex = value_data.get("to_address")
        owner_address = to_base58check_address(bytes.fromhex(owner_hex)) if owner_hex else None
        to_address = to_base58check_address(bytes.fromhex(to_hex)) if to_hex else None

        return jsonify({
            "hash": latest.get("txID"),
            "amount": int(value_data.get("amount", 0)) / 1_000_000,
            "from": owner_address,
            "to": to_address,
            "timestamp": latest.get("block_timestamp"),
            "tronscan": f"https://tronscan.org/#/transaction/{latest.get('txID')}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
