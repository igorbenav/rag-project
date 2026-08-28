"""API key generation and verification. No database involved."""

import pytest

from src.modules.api_key.constants import KEY_PREFIX
from src.modules.api_key.utils import generate_key, lookup_hash, secret_hash, verify


class TestGeneration:
    def test_keys_are_prefixed_so_a_leaked_one_can_be_grepped(self) -> None:
        assert generate_key().startswith(KEY_PREFIX)

    def test_every_key_is_distinct(self) -> None:
        assert len({generate_key() for _ in range(50)}) == 50

    def test_keys_carry_enough_entropy_to_be_unguessable(self) -> None:
        assert len(generate_key()) > 40


class TestLookupHash:
    def test_is_deterministic_so_it_can_index_a_column(self) -> None:
        key = generate_key()

        assert lookup_hash(key) == lookup_hash(key)

    def test_differs_between_keys(self) -> None:
        assert lookup_hash(generate_key()) != lookup_hash(generate_key())

    def test_is_a_sha256_hex_digest(self) -> None:
        digest = lookup_hash(generate_key())

        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")


class TestSecretHash:
    def test_is_salted_so_the_same_key_hashes_differently(self) -> None:
        """A shared salt would let one cracked hash reveal identical keys."""
        key = generate_key()

        assert secret_hash(key) != secret_hash(key)

    def test_verifies_the_key_it_was_made_from(self) -> None:
        key = generate_key()

        assert verify(key, secret_hash(key))

    def test_rejects_a_different_key(self) -> None:
        assert not verify(generate_key(), secret_hash(generate_key()))

    @pytest.mark.parametrize("stored", ["", "not-a-bcrypt-hash", "$2b$12$short"])
    def test_a_malformed_stored_hash_fails_closed(self, stored: str) -> None:
        """A corrupt row must deny access, not raise into a 500."""
        assert not verify(generate_key(), stored)

    def test_the_plaintext_never_appears_in_either_hash(self) -> None:
        key = generate_key()

        assert key not in secret_hash(key)
        assert key not in lookup_hash(key)
