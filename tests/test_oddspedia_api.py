from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

from consensus.oddspedia import collect_oddspedia_feed, validate_feed_url

NOW = datetime(2026, 11, 19, 20, tzinfo=timezone.utc)
TOKEN = "fixture-test-token-123456789"
URL = "https://widgets.oddspedia.com/api/matches?api_token=" + TOKEN + "&lang=en"


class Client:
    def __init__(self, response="[]", error=None):
        self.response, self.error, self.calls = response, error, []

    def get(self, url, **options):
        self.calls.append((url, options))
        if self.error:
            raise self.error
        return self.response


class OddspediaApiTests(unittest.TestCase):
    def test_full_url_and_html_escaped_ampersand_are_supported(self):
        self.assertEqual(validate_feed_url(URL), URL)
        self.assertEqual(validate_feed_url(URL.replace("&lang", "&amp;lang")), URL)

    def test_invalid_configuration_never_makes_a_request_or_echoes_the_value(self):
        bad = ["<a href='"+URL+"'>Open</a>", json.dumps([{"name":"Football"}]), TOKEN,
               "["+URL+"]("+URL+")", URL.replace("widgets.oddspedia.com", "evil.example"),
               URL.replace("widgets.oddspedia.com", "widgets.oddspedia.com.evil.example"),
               URL.replace("https:", "http:"), URL.replace("/api/matches", "/dashboard/api"),
               URL.replace(TOKEN, "xxxxxxxxxxxxx"), URL+"&api_token=another-long-token"]
        for value in bad:
            with self.subTest(value=value):
                client=Client()
                result=collect_oddspedia_feed(NOW,feed_url=value,client=client)
                self.assertEqual(result["reason"],"invalid_configuration")
                self.assertFalse(client.calls)
                self.assertNotIn(TOKEN,json.dumps(result))

    def test_missing_secret_does_not_claim_it_is_connected(self):
        client=Client()
        result=collect_oddspedia_feed(NOW,feed_url="",client=client)
        self.assertEqual(result["status"],"not_configured")
        self.assertFalse(result["configured"])
        self.assertFalse(client.calls)

    def test_json_response_is_read_only_and_never_a_prediction(self):
        client=Client(json.dumps({"data":[{"id":1,"home":"A","away":"B","api_token":TOKEN,"url":URL}]}))
        with patch.dict("os.environ",{"GITHUB_ACTIONS":"false"}):
            result=collect_oddspedia_feed(NOW,feed_url=URL,client=client)
        self.assertEqual(result["status"],"ok")
        self.assertEqual(result["records_received"],1)
        self.assertFalse(result["counts_as_prediction"])
        self.assertFalse(result["used_in_analysis"])
        self.assertNotIn(TOKEN,json.dumps(result))
        self.assertNotIn("api_token",json.dumps(result))
        self.assertEqual(result["response_shape"],{"data":[{"id":"number","home":"string","away":"string"}]})
        self.assertEqual(client.calls[0][1],{"check_robots":False,"headers":{"Accept":"application/json"}})

    def test_catalogue_counts_are_not_presented_as_individual_fixtures(self):
        data=[{"id":1,"name":"Football","slug":"football","match_count":286}]
        result=collect_oddspedia_feed(NOW,feed_url=URL,client=Client(json.dumps(data)))
        self.assertEqual(result["kind"],"sports_catalogue")
        self.assertEqual(result["records_received"],1)
        self.assertNotIn("fixtures",result)

    def test_invalid_json_or_remote_errors_do_not_leak_response_content(self):
        responses=["<html>"+TOKEN+"</html>", "null", json.dumps({"error":TOKEN}),json.dumps({"success":False,"detail":URL})]
        for data in responses:
            result=collect_oddspedia_feed(NOW,feed_url=URL,client=Client(data))
            self.assertEqual(result["status"],"error")
            self.assertNotIn(TOKEN,json.dumps(result))

    def test_network_failure_never_echoes_the_exception_or_request_url(self):
        result=collect_oddspedia_feed(NOW,feed_url=URL,client=Client(error=RuntimeError(URL)))
        self.assertEqual(result["reason"],"request_failed")
        self.assertNotIn(TOKEN,json.dumps(result))
        result=collect_oddspedia_feed(NOW,feed_url=URL,client=Client(error=RuntimeError("HTTP 403")))
        self.assertEqual(result["http_status"],403)


if __name__ == "__main__":
    unittest.main()
