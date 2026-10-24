"""Bounded crawl: opt-in, robots, same-origin, URLs, pacing and no scoring."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import site_audit as site

HTML='''<html><head><title>Page</title><meta name="description" content="Test"/><link rel="canonical" href="https://example.com/"/></head><body><h1>H1</h1><a href="/about">About</a><a href="/private">Private</a><a href="/about?token=secret">Secret</a><a href="https://external.com/a">External</a><a href="http://127.0.0.1/admin">Private IP</a><a href="/login">Login</a></body></html>'''
HTML_ABOUT='''<html><head></head><body><p>Details</p><a href="/">Back</a></body></html>'''


class SiteAuditTests(unittest.TestCase):
    def setUp(self):
        self.root=('https','example.com',443)

    def test_denies_without_two_explicit_flags_before_dependencies(self):
        with patch('site_audit._robot_policy',side_effect=AssertionError('Network accessed')):
            result=site.crawl('https://example.com/')
        self.assertEqual(result['network_requests'],0)
        self.assertEqual(result['pages'],[])
        self.assertEqual(result['outcome'],'blocked')
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(site.main(['https://example.com/','--live','--max-pages','2']),2)
        self.assertEqual(json.loads(out.getvalue())['network_requests'],0)

    def test_query_token_seed_rejected_without_network(self):
        with patch('url_safety.validate_url_strict',side_effect=AssertionError('DNS called')):
            r=site.crawl('https://example.com/?token=secret',allow_live=True)
        self.assertEqual(r['network_requests'],0)
        self.assertEqual(r['outcome'],'blocked')
        self.assertNotIn('secret',json.dumps(r))

    def test_ipv4_private_seed_rejected_before_fetch(self):
        with patch('site_audit._robot_policy',side_effect=AssertionError('Network called')):
            r=site.crawl('https://127.0.0.1/',allow_live=True)
        self.assertEqual(r['outcome'],'blocked')
        self.assertEqual(r['network_requests'],0)

    def test_candidates_reject_scheme_host_credentials_query_and_bad_paths(self):
        rejects=['https://evil.com/a','http://example.com/a',
                 'https://user:password@example.com/','https://example.com/search?q=secret',
                 'https://example.com/a#frag','https://example.com/login',
                 'https://example.com/wp-admin/','https://example.com/report.pdf',
                 'https://example.com/%2fadmin','https://example.com/a/../b',
                 'https://example.com/a%3ftoken=secret','javascript:alert(1)',
                 'file:///etc/passwd','https://example.com/\\@evil.com']
        for bad in rejects:
            with self.subTest(bad=bad):
                self.assertIsNone(site.candidate(bad,self.root))
        self.assertEqual(site.candidate('https://EXAMPLE.com:443/about',self.root),'https://example.com/about')

    def test_root_url_without_slash_is_normalized_for_crawl(self):
        self.assertEqual(site.candidate('https://example.com',self.root),
                         'https://example.com/')

    def test_missing_robots_blocks_before_html(self):
        count=[0]
        def fake(url,*,max_bytes,request_counter):
            self.assertEqual(url,'https://example.com/robots.txt')
            request_counter[0]+=1
            return {'status':404,'type':'text/plain','content':None}
        with patch('site_audit._fetch_once',side_effect=fake),patch('url_safety.validate_url_strict',return_value=('https://example.com/','1.1.1.1')):
            r=site.crawl('https://example.com/',allow_live=True,sleep=lambda _:None)
        self.assertEqual(r['network_requests'],1)
        self.assertEqual(r['outcome'],'blocked')
        self.assertEqual(r['pages'],[])
        self.assertIn('robots.txt',r['stop_reason'])

    def test_robot_disallows_seed_and_others(self):
        requests=[]
        def fake(url,*,max_bytes,request_counter):
            requests.append(url)
            request_counter[0]+=1
            if url.endswith('robots.txt'):
                return {'status':200,'type':'text/plain','content':'User-agent: *\nDisallow: /\n'}
            raise AssertionError('No page should be fetched')
        with patch('site_audit._fetch_once',side_effect=fake),patch('url_safety.validate_url_strict',return_value=('https://example.com/','1.1.1.1')):
            r=site.crawl('https://example.com/',allow_live=True,sleep=lambda _:None)
        self.assertEqual(requests,['https://example.com/robots.txt'])
        self.assertEqual(r['outcome'],'blocked')
        self.assertIn('robots.txt denies',r['stop_reason'])

    def _simulated_site(self, *, robots='User-agent: *\nDisallow: /private\nCrawl-delay: 1\n', html=HTML):
        seen=[]
        def get(url,*,max_bytes,request_counter):
            seen.append(url)
            request_counter[0]+=1
            if url.endswith('/robots.txt'):
                return {'status':200,'type':'text/plain','content':robots}
            if url=='https://example.com/':
                return {'status':200,'type':'text/html; charset=utf-8','content':html}
            if url=='https://example.com/about':
                return {'status':200,'type':'text/html','content':HTML_ABOUT}
            raise AssertionError('Unexpected fetch '+url)
        return seen,get

    def test_real_parser_processes_only_allowed_paths_and_no_secrets(self):
        seen,get=self._simulated_site()
        with patch('site_audit._fetch_once',side_effect=get),patch('url_safety.validate_url_strict',return_value=('https://example.com/','1.1.1.1')):
            r=site.crawl('https://example.com/',allow_live=True,max_pages=5,
                         sleep=lambda _:None,clock=lambda :0)
        self.assertEqual(seen,['https://example.com/robots.txt','https://example.com/','https://example.com/about'])
        self.assertEqual(r['network_requests'],3)
        self.assertEqual(len(r['pages']),2)
        self.assertEqual(r['robots_status'],'checked_and_seed_allowed')
        self.assertEqual(r['outcome'],'observations_only')
        self.assertIsNone(r['seo_score'])
        self.assertNotIn('secret',json.dumps(r))
        self.assertTrue(any(f['id']=='missing-title' for f in r['pages'][1]['findings']))
        self.assertEqual(r['stop_reason'],'discovery_queue_empty')

    def test_canonical_observation_redacts_query_credentials_and_fragment(self):
        markup=HTML.replace('https://example.com/"', 'https://user:pass@example.com/pricing?secret=HIDDEN#frag"')
        seen,get=self._simulated_site(html=markup)
        with patch('site_audit._fetch_once',side_effect=get),patch('url_safety.validate_url_strict',return_value=('https://example.com/','1.1.1.1')):
            r=site.crawl('https://example.com/',allow_live=True,max_pages=1,
                         sleep=lambda _:None,clock=lambda :0)
        data=json.dumps(r)
        self.assertNotIn('HIDDEN',data)
        self.assertNotIn('user:pass',data)
        self.assertEqual(r['pages'][0]['observations']['canonical'],'https://example.com/pricing')

    def test_limits_pages_and_discovered_links(self):
        seen,get=self._simulated_site()
        with patch('site_audit._fetch_once',side_effect=get),patch('url_safety.validate_url_strict',return_value=('https://example.com/','1.1.1.1')):
            r=site.crawl('https://example.com/',allow_live=True,max_pages=1,sleep=lambda _:None,clock=lambda :0)
        self.assertEqual(r['stop_reason'],'page_limit_reached')
        self.assertEqual(len(r['pages']),1)
        self.assertEqual(r['network_requests'],2)
        self.assertLessEqual(r['discovered_candidate_count'],site.MAX_LINKS_QUEUED)

    def test_429_stops_without_retry(self):
        seen,get=self._simulated_site()
        def fake(url,*,max_bytes,request_counter):
            if url.endswith('/robots.txt'):return get(url,max_bytes=max_bytes,request_counter=request_counter)
            seen.append(url);request_counter[0]+=1
            return {'status':429,'type':'text/html','content':None}
        with patch('site_audit._fetch_once',side_effect=fake),patch('url_safety.validate_url_strict',return_value=('https://example.com/','1.1.1.1')):
            r=site.crawl('https://example.com/',allow_live=True,sleep=lambda _:None)
        self.assertEqual(r['outcome'],'partial')
        self.assertEqual(r['network_requests'],2)
        self.assertIn('429',r['stop_reason'])

    def test_redirect_cannot_leak_to_another_origin_or_query(self):
        for target in ('https://evil.example/hit','http://127.0.0.1/a','/about?token=secret'):
            with self.subTest(target=target):
                requested=[]
                def fake(url,*,max_bytes,request_counter):
                    requested.append(url);request_counter[0]+=1
                    return {'status':302,'location':target,'content':None,'type':'text/html'}
                with patch('site_audit._fetch_once',side_effect=fake):
                    with self.assertRaises(site.CrawlBlocked):
                        site.fetch('https://example.com/',self.root,max_bytes=100,
                                   counter=[0],pacer=[None],sleep=lambda _:None,clock=lambda :0)
                self.assertEqual(requested,['https://example.com/'])

    def test_redirect_into_robots_disallowed_path_never_fetched(self):
        seen=[]
        def fake(url,*,max_bytes,request_counter):
            seen.append(url);request_counter[0]+=1
            return {'status':301,'location':'/private','content':None,'type':'text/html'}
        with patch('site_audit._fetch_once',side_effect=fake):
            with self.assertRaisesRegex(site.CrawlBlocked,'robots.txt denied'):
                site.fetch('https://example.com/',self.root,max_bytes=100,
                          counter=[0],pacer=[None],sleep=lambda _:None,clock=lambda :0,
                          can_fetch=lambda dest: '/private' not in dest)
        self.assertEqual(seen,['https://example.com/'])

    def test_private_host_opt_in_environment_does_not_allow_site_crawl(self):
        with patch('site_audit._robot_policy',side_effect=AssertionError('network')), \
             patch('url_safety.validate_url_strict',return_value=('https://127.0.0.1/','127.0.0.1')):
            r=site.crawl('https://127.0.0.1/',allow_live=True)
        self.assertEqual(r['outcome'],'blocked')
        self.assertEqual(r['network_requests'],0)

    def test_malformed_robots_without_user_agent_fails_closed(self):
        seen,get=self._simulated_site(robots='Sitemap: https://example.com/sitemap.xml\n')
        with patch('site_audit._fetch_once',side_effect=get),patch('url_safety.validate_url_strict',return_value=('https://example.com/','1.1.1.1')):
            r=site.crawl('https://example.com/',allow_live=True,sleep=lambda _:None)
        self.assertEqual(r['network_requests'],1)
        self.assertEqual(r['outcome'],'blocked')

    def test_same_origin_redirect_is_bounded(self):
        requested=[]
        def fake(url,*,max_bytes,request_counter):
            requested.append(url);request_counter[0]+=1
            if url.endswith('/about'):
                return {'status':200,'location':None,'content':'ok','type':'text/html'}
            return {'status':301,'location':'/about','content':None,'type':'text/html'}
        with patch('site_audit._fetch_once',side_effect=fake):
            response=site.fetch('https://example.com/',self.root,max_bytes=100,
                                counter=[0],pacer=[None],sleep=lambda _:None,clock=lambda :0)
        self.assertEqual(response['final_url'],'https://example.com/about')
        self.assertEqual(len(requested),2)

    def test_crawl_delay_above_budget_blocks(self):
        seen,get=self._simulated_site(robots='User-agent: *\nCrawl-delay: 99\nAllow: /\n')
        with patch('site_audit._fetch_once',side_effect=get),patch('url_safety.validate_url_strict',return_value=('https://example.com/','1.1.1.1')):
            r=site.crawl('https://example.com/',allow_live=True,sleep=lambda _:None)
        self.assertEqual(r['outcome'],'blocked')
        self.assertEqual(r['network_requests'],1)

    def test_bounds_on_user_inputs_fail_without_fetch(self):
        for pages,bytes_ in ((0,100),(13,100),(2,0),(2,2097153),(-1,999)):
            with self.subTest(pages=pages,bytes_=bytes_), patch('site_audit._fetch_once',side_effect=AssertionError('network')):
                r=site.crawl('https://example.com/',allow_live=True,max_pages=pages,max_bytes=bytes_)
                self.assertEqual(r['outcome'],'blocked')
                self.assertEqual(r['network_requests'],0)

    def test_markdown_is_observation_not_aggregate_rank_claim(self):
        r=site.crawl('https://example.com/')
        md=site.markdown_report(r)
        self.assertIn('not a site-wide completeness or ranking claim',md)
        self.assertNotIn('SEO health score',md)

    def test_only_manual_requests_skip_automatic_redirects(self):
        calls=[]
        class Response:
            status_code=302
            headers={'Location':'https://evil.com','Content-Type':'text/html'}
            def __enter__(self):return self
            def __exit__(self,*args):return None
        with patch('url_safety.safe_requests_get',side_effect=lambda url,**kw:(calls.append((url,kw)) or Response())):
            r=site._fetch_once('https://example.com/',max_bytes=100,request_counter=[0])
        self.assertEqual(r['status'],302)
        self.assertFalse(calls[0][1]['allow_redirects'])
        self.assertTrue(calls[0][1]['stream'])
        self.assertEqual(calls[0][1]['timeout'],(5,12))


if __name__=='__main__':unittest.main()
