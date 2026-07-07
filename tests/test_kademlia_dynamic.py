from kademlia_dynamic import (
    xor_distance, hash_key_to_node_id, generate_node_id,
    compute_cache_ttl, node_id_to_binary, KademliaServer,
)


def test_xor_distance_to_self_is_zero():
    nid = generate_node_id()
    assert xor_distance(nid, nid) == 0


def test_xor_distance_is_symmetric():
    a = generate_node_id()
    b = generate_node_id()
    assert xor_distance(a, b) == xor_distance(b, a)


def test_hash_key_is_deterministic_hex():
    h1 = hash_key_to_node_id("lobby-key")
    h2 = hash_key_to_node_id("lobby-key")
    assert h1 == h2
    int(h1, 16)  # valid hex


def test_generate_node_id_length_matches_binary():
    nid = generate_node_id()
    assert len(node_id_to_binary(nid)) == 160


def test_cache_ttl_respects_minimum():
    a = generate_node_id()
    b = generate_node_id()
    ttl = compute_cache_ttl(a, b, key_expiry_seconds=86410, min_cache_ttl_seconds=600)
    assert ttl >= 600


def test_server_constructs_with_defaults():
    server = KademliaServer()
    assert server is not None
