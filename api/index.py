from flask import Flask, jsonify
from tronpy import Tron
from tronpy.keys import PrivateKey
import secrets

app = Flask(__name__)

client = Tron()  # For mainnet
# client = Tron(network="shasta")  # For testnet

ADMIN_ADDRESS = "TVwXueNC13YUwTJnRvfK9An1cF39Q1af8Q"
ADMIN_FEE_PERCENT = 2

@app.route("/")
def home():
    return "✅ TRON API is live on Vercel"

@app.route("/wallet", methods=["GET"])
def generate_wallet():
    hex_key = secrets.token_hex(32)
    priv_key = PrivateKey(bytes.fromhex(hex_key))
    address = priv_key.public_key.to_base58check_address()
    return jsonify({
        "address": address,
        "private_key": priv_key.hex()
    })

@app.route("/balance/<address>", methods=["GET"])
def get_balance(address):
    try:
        acc = client.get_account(address)
        balance = acc.get("balance", 0) / 1_000_000
        return jsonify({"address": address, "balance": balance})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/pay/<private_key>/<to_address>/<amount>", methods=["GET"])
def pay(private_key, to_address, amount):
    try:
        pk = PrivateKey(bytes.fromhex(private_key.replace("0x", "")))
        from_address = pk.public_key.to_base58check_address()

        amount = float(amount)
        fee = round((ADMIN_FEE_PERCENT / 100) * amount, 6)
        to_user = round(amount - fee, 6)

        txs = []

        tx1 = (
            client.trx.transfer(from_address, to_address, int(to_user * 1_000_000))
            .memo("User Payment")
            .build()
            .sign(pk)
        )
        txs.append({
            "to": to_address,
            "amount": to_user,
            "tx_id": tx1.broadcast().txid
        })

        tx2 = (
            client.trx.transfer(from_address, ADMIN_ADDRESS, int(fee * 1_000_000))
            .memo("Admin Fee")
            .build()
            .sign(pk)
        )
        txs.append({
            "to": ADMIN_ADDRESS,
            "amount": fee,
            "tx_id": tx2.broadcast().txid
        })

        return jsonify({
            "from": from_address,
            "total_sent": amount,
            "transactions": txs
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/history/<address>", methods=["GET"])
def history(address):
    return jsonify({
        "tronscan": f"https://tronscan.org/#/address/{address}"
    })

# Required for Vercel Python
def handler(event, context):
    return app(event, context)
