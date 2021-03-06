import csv
import os
import re
from datetime import timedelta

import boto3
import mock
import six

from ichnaea.data.public import (
    write_stations_to_csv,
)
from ichnaea.data.tasks import (
    cell_export_full,
    cell_export_diff,
)
from ichnaea.models import (
    Radio,
)
from ichnaea.tests.factories import CellShardFactory
from ichnaea import util

CELL_FIELDS = [
    'radio', 'mcc', 'mnc', 'lac', 'cid', 'psc',
    'lon', 'lat', 'range', 'samples', 'changeable',
    'created', 'updated', 'averageSignal']


class FakeTask(object):

    def __init__(self, app):
        self.app = app


class TestExport(object):

    def test_local_export(self, celery, session):
        now = util.utcnow()
        today = now.date()
        long_ago = now - timedelta(days=367)
        cell_fixture_fields = (
            'radio', 'cid', 'lat', 'lon', 'mnc', 'mcc', 'lac')
        base_cell = CellShardFactory.build(radio=Radio.wcdma)
        cell_key = {'radio': Radio.wcdma, 'mcc': base_cell.mcc,
                    'mnc': base_cell.mnc, 'lac': base_cell.lac}
        cells = set()

        for cid in range(190, 200):
            cell = dict(cid=cid, lat=base_cell.lat,
                        lon=base_cell.lon, **cell_key)
            CellShardFactory(**cell)
            cell['lat'] = '%.7f' % cell['lat']
            cell['lon'] = '%.7f' % cell['lon']

            cell['radio'] = 'UMTS'
            cell_strings = [
                (field, str(value)) for (field, value) in cell.items()]
            cell_tuple = tuple(sorted(cell_strings))
            cells.add(cell_tuple)

        # add one incomplete / unprocessed cell
        CellShardFactory(cid=210, lat=None, lon=None, **cell_key)
        # add one really old cell
        CellShardFactory(cid=220, created=long_ago, modified=long_ago,
                         last_seen=long_ago.date(), **cell_key)
        session.commit()

        with util.selfdestruct_tempdir() as temp_dir:
            path = os.path.join(temp_dir, 'export.csv.gz')
            write_stations_to_csv(session, path, today)

            with util.gzip_open(path, 'r') as gzip_wrapper:
                with gzip_wrapper as gzip_file:
                    reader = csv.DictReader(gzip_file, CELL_FIELDS)

                    header = six.next(reader)
                    assert 'area' in header.values()

                    exported_cells = set()
                    for exported_cell in reader:
                        exported_cell_filtered = [
                            (field, value) for (field, value)
                            in exported_cell.items()
                            if field in cell_fixture_fields]
                        exported_cell = tuple(sorted(exported_cell_filtered))
                        exported_cells.add(exported_cell)

                    assert cells == exported_cells

    def test_export_diff(self, celery, session):
        CellShardFactory.create_batch(10, radio=Radio.gsm)
        session.commit()
        pattern = re.compile(
            r'MLS-diff-cell-export-\d+-\d+-\d+T\d+0000\.csv\.gz')

        mock_conn = mock.MagicMock()
        mock_bucket = mock.MagicMock(name='bucket')
        mock_obj = mock.MagicMock()
        mock_conn.return_value.Bucket.return_value = mock_bucket
        mock_bucket.Object.return_value = mock_obj

        with mock.patch.object(boto3, 'resource', mock_conn):
            cell_export_diff(_bucket='bucket')

        s3_key = mock_bucket.Object.call_args[0][0]
        assert pattern.search(s3_key)

        tmp_file = mock_obj.upload_file.call_args[0][0]
        assert pattern.search(tmp_file)

    def test_export_full(self, celery, session):
        now = util.utcnow()
        long_ago = now - timedelta(days=367)
        CellShardFactory.create_batch(10, radio=Radio.gsm)
        CellShardFactory(
            radio=Radio.gsm, created=long_ago,
            modified=long_ago, last_seen=long_ago.date())
        session.commit()
        pattern = re.compile(
            r'MLS-full-cell-export-\d+-\d+-\d+T000000\.csv\.gz')

        mock_conn = mock.MagicMock()
        mock_bucket = mock.MagicMock(name='bucket')
        mock_obj = mock.MagicMock()
        mock_conn.return_value.Bucket.return_value = mock_bucket
        mock_bucket.Object.return_value = mock_obj

        with mock.patch.object(boto3, 'resource', mock_conn):
            cell_export_full(_bucket='bucket')

        s3_key = mock_bucket.Object.call_args[0][0]
        assert pattern.search(s3_key)

        tmp_file = mock_obj.upload_file.call_args[0][0]
        assert pattern.search(tmp_file)
