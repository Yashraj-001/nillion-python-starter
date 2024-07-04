import asyncio
import py_nillion_client as nillion
import os
from dotenv import load_dotenv
from nillion_python_helpers import get_quote_and_pay, create_nillion_client, create_payments_config
from cosmpy.aerial.client import LedgerClient
from cosmpy.aerial.wallet import LocalWallet
from cosmpy.crypto.keypairs import PrivateKey

home = os.getenv("HOME")
load_dotenv(f"{home}/.config/nillion/nillion-devnet.env")

async def main():
    cluster_id = os.getenv("NILLION_CLUSTER_ID")
    grpc_endpoint = os.getenv("NILLION_NILCHAIN_GRPC")
    chain_id = os.getenv("NILLION_NILCHAIN_CHAIN_ID")

    seed = "my_seed"
    userkey = nillion.UserKey.from_seed(seed)
    nodekey = nillion.NodeKey.from_seed(seed)

    client = create_nillion_client(userkey, nodekey)
    party_id = client.party_id
    user_id = client.user_id

    current_dir = os.path.dirname(__file__)
    program_mir_path = os.path.join(current_dir, '../nada_quickstart_programs/target/secret_addition_complete.nada.bin')

    try:
        if not os.path.exists(program_mir_path):
            print(f"Error: Program file not found at {program_mir_path}")
            return
    except Exception as e:
        print(f"Error: {e}")
        return

    payments_config = create_payments_config(chain_id, grpc_endpoint)
    payments_client = LedgerClient(payments_config)
    payments_wallet = LocalWallet(
        PrivateKey(bytes.fromhex(os.getenv("NILLION_NILCHAIN_PRIVATE_KEY_0"))),
        prefix="nillion",
    )

    try:
        receipt_store_program = await get_quote_and_pay(
            client,
            nillion.Operation.store_program(program_mir_path),
            payments_wallet,
            payments_client,
            cluster_id,
        )
    except ValueError as e:
        print(f"Error: {e}")
        return

    action_id = await client.store_program(
        cluster_id, "secret_addition_complete", program_mir_path, receipt_store_program
    )

    program_id = f"{user_id}/secret_addition_complete"
    print("Stored program. action_id:", action_id)
    print("Stored program_id:", program_id)

    new_secret = nillion.NadaValues(
        {
            "my_int1": nillion.SecretInteger(500),
        }
    )

    party_name = "Party1"
    party_id_2 = "Party2"
    party_id_3 = "Party3"
    permissions = nillion.Permissions.default_for_user(client.user_id)
    permissions.add_compute_permissions({client.user_id: {program_id}})

    try:
        receipt_store = await get_quote_and_pay(
            client,
            nillion.Operation.store_values(new_secret, ttl_days=5),
            payments_wallet,
            payments_client,
            cluster_id,
        )
    except ValueError as e:
        print(f"Error: {e}")
        return

    store_id = await client.store_values(
        cluster_id, new_secret, permissions, receipt_store
    )
    print(f"Computing using program {program_id}")
    print(f"Use secret store_id: {store_id}")

    compute_bindings = nillion.ProgramBindings(program_id)
    compute_bindings.add_input_party(party_name, party_id)
    compute_bindings.add_input_party("Party2", party_id_2)
    compute_bindings.add_output_party("Party3", party_id_3)

    computation_time_secrets = nillion.NadaValues({"my_int2": nillion.SecretInteger(10)})

    try:
        receipt_compute = await get_quote_and_pay(
            client,
            nillion.Operation.compute(program_id, computation_time_secrets),
            payments_wallet,
            payments_client,
            cluster_id,
        )
    except ValueError as e:
        print(f"Error: {e}")
        return

    compute_id = await client.compute(
        cluster_id,
        compute_bindings,
        [store_id],
        computation_time_secrets,
        receipt_compute,
    )

    print(f"The computation was sent to the network. compute_id: {compute_id}")
    while True:
        compute_event = await client.next_compute_event()
        if isinstance(compute_event, nillion.ComputeFinishedEvent):
            print(f"✅  Compute complete for compute_id {compute_event.uuid}")
            print(f"🖥️  The result is {compute_event.result.value}")
            return compute_event.result.value

if __name__ == "__main__":
    asyncio.run(main())