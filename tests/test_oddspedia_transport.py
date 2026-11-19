from datetime import timedelta
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
from unittest import TestCase
from unittest.mock import patch

from consensus.oddspedia import collect_oddspedia_feed
from consensus.oddspedia_transport import classify_denial, OddspediaClient, ApiAccessError
from test_oddspedia_api import URL, TOKEN, NOW, Client


class TransportTests(TestCase):
    def test_a_generic_403_is_not_invented_as_a_bad_key_or_bot_block(self):
        error=classify_denial(403,{},"Forbidden "+TOKEN)
        self.assertEqual(error.reason,"access_denied")
        self.assertNotIn(TOKEN,str(error))

    def test_known_error_messages_are_classified_without_exposing_raw_data(self):
        examples=[('Invalid API token '+TOKEN,'credential_rejected'),
                  ('Domain is not licensed '+URL,'domain_rejected'),
                  ('API access is disabled '+TOKEN,'account_rejected'),
                  ('Verify you are human '+TOKEN,'provider_challenge')]
        for body,reason in examples:
            error=classify_denial(403,{},body)
            self.assertEqual(error.reason,reason)
            self.assertNotIn(TOKEN,str(error))
        headers=Message();headers['CF-Mitigated']='challenge'
        self.assertEqual(classify_denial(403,headers,'').reason,'provider_challenge')
        self.assertEqual(classify_denial(429,{},'').reason,'rate_limited')

    def test_http_error_body_is_read_privately_and_safe_metadata_reaches_the_app(self):
        headers=Message();headers['Content-Type']='text/html';headers['CF-Mitigated']='challenge'
        remote=HTTPError(URL,403,'Forbidden',headers,BytesIO(('<html>Verify you are human '+TOKEN+'</html>').encode()))
        with patch('consensus.oddspedia_transport.build_opener') as opener:
            opener.return_value.open.side_effect=remote
            result=collect_oddspedia_feed(NOW,feed_url=URL)
        self.assertEqual(result['reason'],'provider_challenge')
        self.assertEqual(result['response_type'],'html')
        self.assertEqual(result['http_status'],403)
        self.assertNotIn(TOKEN,str(result))
        self.assertEqual(opener.return_value.open.call_count,1)
        self.assertEqual(result['next_check_at'],(NOW+timedelta(hours=6)).isoformat())

    def test_html_at_status_200_is_not_a_successful_json_api(self):
        class Response:
            status=200;headers={'Content-Type':'text/html'}
            def read(self,limit):return b'<html><h1>Site Unavailable</h1></html>'
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with patch('consensus.oddspedia_transport.build_opener') as opener:
            opener.return_value.open.return_value=Response()
            result=collect_oddspedia_feed(NOW,feed_url=URL)
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['reason'],'unexpected_html')

    def test_credentials_are_not_sent_to_another_host_or_undocumented_route(self):
        with patch('consensus.oddspedia_transport.build_opener') as opener:
            for url in [URL.replace('widgets.oddspedia.com','other.example'),URL.replace('/api/matches','/dashboard/api')]:
                with self.assertRaises(ApiAccessError):OddspediaClient().get(url)
            opener.assert_not_called()

    def test_redirect_is_not_followed_with_the_credential(self):
        headers=Message();headers['Location']='https://other.example/'+TOKEN
        remote=HTTPError(URL,302,'Found',headers,BytesIO(b''))
        with patch('consensus.oddspedia_transport.build_opener') as opener:
            opener.return_value.open.side_effect=remote
            result=collect_oddspedia_feed(NOW,feed_url=URL)
        self.assertEqual(result['reason'],'unexpected_redirect')
        self.assertEqual(opener.return_value.open.call_count,1)
        self.assertNotIn(TOKEN,str(result))

    def test_backoff_reuses_the_original_timestamp_and_manual_recheck_can_run(self):
        previous=collect_oddspedia_feed(NOW,feed_url=URL,client=Client(error=RuntimeError('HTTP 403')))
        client=Client()
        result=collect_oddspedia_feed(NOW+timedelta(minutes=30),feed_url=URL,client=client,previous=previous)
        self.assertTrue(result['deferred']);self.assertFalse(client.calls)
        self.assertEqual(result['checked_at'],NOW.isoformat())
        result=collect_oddspedia_feed(NOW+timedelta(minutes=30),feed_url=URL,client=client,previous=previous,force=True)
        self.assertEqual(len(client.calls),1)
        self.assertNotIn('deferred',result)

    def test_a_challenge_at_http_200_is_also_paused(self):
        client=Client(error=ApiAccessError(200,'provider_challenge','Verificação exigida.','html'))
        previous=collect_oddspedia_feed(NOW,feed_url=URL,client=client)
        self.assertEqual(previous['next_check_at'],(NOW+timedelta(hours=6)).isoformat())
        client=Client()
        result=collect_oddspedia_feed(NOW+timedelta(hours=1),feed_url=URL,client=client,previous=previous)
        self.assertTrue(result['deferred']);self.assertFalse(client.calls)
