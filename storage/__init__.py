import boto3

import config

GENERIC_AD_PATH = 'mobile/ads/%d/%s.html'


def _get_ad_key(ad_id):
    filename = 'data'
    return GENERIC_AD_PATH % (ad_id, filename)


def save_ad(ad_id, html):
    object = _get_bucket().put_object(Key=_get_ad_key(ad_id), Body=html)
    return True


def load_ad(ad_id):
    s3_object = _get_bucket().get_object(Key=_get_ad_key(ad_id))
    return s3_object["Body"].read()


def is_stored(ad_id):
    ad_key = _get_ad_key(ad_id)
    objs = list(_get_bucket().objects.filter(Prefix=ad_key))
    if len(objs) > 0 and objs[0].key == ad_key:
        return True
    return False


def _get_bucket():
    s3 = boto3.resource('s3')
    return s3.Bucket(config.S3_BUCKET_NAME)
