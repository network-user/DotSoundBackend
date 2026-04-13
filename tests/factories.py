import factory

from app.models.album import Album
from app.models.comment import TrackComment
from app.models.complaint import Complaint
from app.models.follow import UserFollow
from app.models.like import Like
from app.models.playlist import Playlist
from app.models.track import Track
from app.models.user import User


class UserFactory(factory.Factory):
    class Meta:
        model = User

    telegram_id = factory.Sequence(lambda n: 100_000 + n)
    first_name = factory.Faker("first_name")
    username = factory.LazyAttribute(
        lambda o: f"user_{o.telegram_id}"
    )
    is_active = True
    is_admin = False
    auth_provider = "telegram"


class TrackFactory(factory.Factory):
    class Meta:
        model = Track

    title = factory.Faker("sentence", nb_words=3)
    artist = factory.Faker("name")
    is_active = True
    is_public = True
    processing_status = "active"
    source = "internal"


class AlbumFactory(factory.Factory):
    class Meta:
        model = Album

    title = factory.Faker("sentence", nb_words=2)
    is_public = True


class PlaylistFactory(factory.Factory):
    class Meta:
        model = Playlist

    name = factory.Faker("sentence", nb_words=2)
    is_public = True


class LikeFactory(factory.Factory):
    class Meta:
        model = Like


class UserFollowFactory(factory.Factory):
    class Meta:
        model = UserFollow


class ComplaintFactory(factory.Factory):
    class Meta:
        model = Complaint

    reason = factory.Faker("sentence")
    is_resolved = False


class TrackCommentFactory(factory.Factory):
    class Meta:
        model = TrackComment

    text = factory.Faker("sentence")
    is_pinned = False
    is_hidden_by_author = False
    is_deleted = False
