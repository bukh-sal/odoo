"""Untrusted origin spelling cannot become edge configuration or redirects."""
import configparser
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mp_http_profile',ROOT/'tools/http_profile.py');profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)


class HTTPProfileTests(unittest.TestCase):
    def test_canonical_origin_and_port_are_kept_without_normalizing_bad_input(self):
        for value in ['https://platform.example.test','https://security.localhost:18443','https://xn--bcher-kva.example']:
            self.assertEqual(profile.production_origin(value)[0],value)

    def test_origin_injection_path_userinfo_wildcards_and_ambiguous_ports_fail(self):
        for value in [None,'','http://host','HTTPS://host','https://Host',' https://host','https://host/','https://host?debug=1','https://user@host','https://*.example','https://host;include','https://host\nserver {}','https://host:443','https://host:0','https://host:65536','https://host:xyz','https://bad..host','https://-bad.host','https://bad-.host','https://bücher.example','https://host#fragment','https://host%2fother','https://host:0443','https://host:018443']:
            with self.subTest(value=value),self.assertRaises(ValueError):profile.production_origin(value)

    def test_only_explicit_supported_profile_combinations_are_accepted(self):
        for mode,origin in [('unknown',None),('production',None),('development','https://host')]:
            with self.subTest(mode=mode),self.assertRaises(ValueError):profile.render(mode,origin)

    def test_production_config_cannot_enable_db_listing_dev_or_untrusted_proxy(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'odoo.conf';base=dict(db_name='mp_disposable_r0_r1_http',dbfilter='^mp_disposable_r0_r1_http$',proxy_mode='True',list_db='False',log_handler=':INFO,werkzeug:ERROR')
            for change in [dict(proxy_mode='False'),dict(list_db='True'),dict(dbfilter='.*'),dict(db_name='a,b'),dict(dev_mode='all'),dict(test_enable='True'),dict(log_handler=':INFO')]:
                config=configparser.ConfigParser();config['options']=base|change
                with path.open('w',encoding='utf8') as stream:config.write(stream)
                with self.subTest(change=change),self.assertRaises(ValueError):profile.validate_production_config(path)
            config['options']=base
            with path.open('w',encoding='utf8') as stream:config.write(stream)
            self.assertTrue(profile.validate_production_config(path)['proxy_mode'])

    def test_checked_in_development_config_matches_reviewed_generator(self):
        self.assertEqual((ROOT/'deploy/nginx-r0.conf').read_text(encoding='utf8'),profile.render('development'))


if __name__=='__main__':unittest.main()
