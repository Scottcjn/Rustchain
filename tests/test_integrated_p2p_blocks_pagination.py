import integrated_node


class DummyBlockSync:
    def __init__(self):
        self.calls = []

    def get_blocks_for_sync(self, start_height, limit):
        self.calls.append((start_height, limit))
        return []


def test_parse_p2p_blocks_pagination_rejects_unsafe_values():
    invalid = [
        ({"start": "abc"}, "start must be an integer"),
        ({"start": "-1"}, "start must be >= 0"),
        ({"limit": "abc"}, "limit must be an integer"),
        ({"limit": "0"}, "limit must be >= 1"),
        ({"limit": "-1"}, "limit must be >= 1"),
    ]

    for args, expected_error in invalid:
        values, error_response = integrated_node._parse_p2p_blocks_pagination(args)

        assert values is None
        assert error_response == (expected_error, 400)


def test_parse_p2p_blocks_pagination_caps_limit():
    values, error_response = integrated_node._parse_p2p_blocks_pagination(
        {"start": "7", "limit": "5000"}
    )

    assert error_response is None
    assert values == (7, 1000)
