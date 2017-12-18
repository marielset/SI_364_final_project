"""creating saved friends

Revision ID: e3b2d9eb7b61
Revises: 64e9a13887d3
Create Date: 2017-12-17 16:25:28.832032

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3b2d9eb7b61'
down_revision = '64e9a13887d3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('collections')
    op.create_unique_constraint(None, 'person', ['name'])
    op.drop_constraint('person_email_fkey', 'person', type_='foreignkey')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_foreign_key('person_email_fkey', 'person', 'users', ['email'], ['email'])
    op.drop_constraint(None, 'person', type_='unique')
    op.create_table('collections',
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('song_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['song_id'], ['songs.id'], name='collections_song_id_fkey'),
    sa.ForeignKeyConstraint(['user_id'], ['person.id'], name='collections_user_id_fkey')
    )
    # ### end Alembic commands ###
