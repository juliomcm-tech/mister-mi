from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from consensus.oddspedia import collect_oddspedia_feed, validate_feed_url

NOW = datetime(2026, 11, 19, 20, tzinfo=timezone.utc)
TOKEN = "fixture-test-token-123456789"
URL = "https://widgets.oddspedia.com/api/matches?api_token=" + TOKEN + "&lang=en"


CATALOGUE = [{"id":1,"name":"Football","slug":"football","match_count":286},
             {"id":5,"name":"Tennis","slug":"tennis","match_count":209}]


class Client:
    def __init__(self, response=None, error=None, search=None):
        self.response, self.error, self.calls, self.search = response, error, [], search

    def get(self, url, **options):
        self.calls.append((url, options))
        if self.error:
            raise self.error
        if urlsplit(url).path == "/api/search":
            if isinstance(self.search, Exception):
                raise self.search
            return self.search if self.search is not None else "[]"
        return self.response if self.response is not None else json.dumps(CATALOGUE)


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

    def test_documented_catalogue_is_used_instead_of_the_unfiltered_matches_url(self):
        rows=[{**CATALOGUE[0],"api_token":TOKEN,"url":URL}]
        client=Client(json.dumps({"data":rows}))
        with patch.dict("os.environ",{"GITHUB_ACTIONS":"false"}):
            result=collect_oddspedia_feed(NOW,feed_url=URL,client=client)
        self.assertEqual(result["status"],"partial")
        self.assertEqual(result["sports_count"],1)
        self.assertEqual(result["records_received"],1)
        self.assertFalse(result["counts_as_prediction"])
        self.assertFalse(result["used_in_analysis"])
        self.assertNotIn(TOKEN,json.dumps(result))
        self.assertNotIn("api_token",json.dumps(result))
        self.assertEqual(result["response_shape"],{"data":[{"id":"number","name":"string","slug":"string","match_count":"number"}]})
        self.assertEqual(urlsplit(client.calls[0][0]).path,"/api/sports")
        self.assertEqual(client.calls[0][1],{"check_robots":False,"headers":{"Accept":"application/json"}})

    def test_search_has_one_lowercase_team_per_request_and_is_bounded(self):
        client=Client(search=json.dumps({"data":[{"id":42,"home":"Example","api_token":TOKEN}]}))
        queries=["BAYERN Munich","  bayern   munich  ","Carlos Alcaraz",*["Team "+str(i) for i in range(12)]]
        result=collect_oddspedia_feed(NOW,feed_url=URL,client=client,queries=queries)
        self.assertEqual(len(client.calls),7)
        self.assertEqual(len(result["searches"]),6)
        self.assertEqual(result["status"],"ok")
        for url,options in client.calls[1:]:
            parsed=urlsplit(url);params=parse_qs(parsed.query)
            self.assertEqual(parsed.path,"/api/search")
            self.assertEqual(params["q"],[params["q"][0].lower()])
            self.assertEqual(params["api_token"],[TOKEN])
            self.assertNotIn("from",params)
            self.assertNotIn("to",params)
        self.assertEqual(parse_qs(urlsplit(client.calls[1][0]).query)["q"],["bayern munich"])
        self.assertFalse(result["used_in_analysis"])
        self.assertNotIn(TOKEN,json.dumps(result))
        self.assertEqual(result["search_records_received"],6)

    def test_empty_data_text_and_json_empty_results_are_not_403_or_malformed_json(self):
        for raw in ["Empty data", '"Empty data"',"[]",'{"data":[]}']:
            client=Client(search=raw)
            result=collect_oddspedia_feed(NOW,feed_url=URL,client=client,queries=["Example Team"])
            self.assertEqual(result["status"],"empty")
            self.assertEqual(result["searches"][0]["reason"],"empty_response")
            self.assertEqual(result["search_records_received"],0)
        result=collect_oddspedia_feed(NOW,feed_url=URL,client=Client("Empty data"),queries=["Example Team"])
        self.assertEqual(result["status"],"empty")
        self.assertEqual(result["endpoint"],"/api/sports")

    def test_refusal_stops_requests_and_does_not_probe_other_routes(self):
        client=Client(error=RuntimeError("HTTP 403"))
        result=collect_oddspedia_feed(NOW,feed_url=URL,client=client,queries=["One","Two"])
        self.assertEqual(len(client.calls),1)
        self.assertEqual(result["http_status"],403)
        self.assertEqual(result["endpoint"],"/api/sports")
        client=Client(search=RuntimeError("HTTP 403"))
        result=collect_oddspedia_feed(NOW,feed_url=URL,client=client,queries=["One","Two"])
        self.assertEqual(len(client.calls),2)
        self.assertEqual(result["status"],"partial")
        self.assertEqual(result["reason"],"search_failed")

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
