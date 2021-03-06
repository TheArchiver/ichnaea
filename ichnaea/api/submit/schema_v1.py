"""
Colander schemata describing the public v1/geosubmit HTTP API.
"""

import colander

from ichnaea.api.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.api.submit.schema import (
    CellTowerSchema,
    PositionSchema,
    ReportSchema,
)


class ReportV1Schema(PositionSchema, ReportSchema):

    _position_fields = (
        'latitude',
        'longitude',
        'accuracy',
        'altitude',
        'altitudeAccuracy',
        'age',
        'heading',
        'pressure',
        'speed',
        'source',
    )

    @colander.instantiate(missing=())
    class cellTowers(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(CellTowerSchema):

            psc = OptionalIntNode(to_name='primaryScramblingCode')

    def deserialize(self, data):
        data = super(ReportV1Schema, self).deserialize(data)
        if (data is colander.drop or data is colander.null):
            return data
        position_data = {}
        for field in self._position_fields:
            if field in data:
                position_data[field] = data[field]
                del data[field]
        if position_data:
            data['position'] = position_data
        return data


class SubmitV1Schema(OptionalMappingSchema):

    @colander.instantiate()
    class items(OptionalSequenceSchema):  # NOQA
        report = ReportV1Schema()


SUBMIT_V1_SCHEMA = SubmitV1Schema()
