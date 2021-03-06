import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import threading
from tables import Base, Summoner
from tables.enums import Tier, Rank, Server
import logging
import asyncio
import aioredis


class Worker(threading.Thread):

    def __init__(self, echo=False):
        super().__init__()
        self.engine = create_engine(
            f'postgresql://%s@%s:%s/data' %
            (os.environ['POSTGRES_USER'],
             os.environ['POSTGRES_HOST'],
             os.environ['POSTGRES_PORT']),
            echo=echo)

        Base.metadata.create_all(self.engine)
        self.server = os.environ['SERVER']
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.stopped = False

        self.logging = logging.getLogger("DBConnector")
        self.logging.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter('%(asctime)s [DBConnector] %(message)s'))
        self.logging.addHandler(handler)

        self.redisc = None

    def shutdown(self):
        """Set stopping flag.

        Handler called by the sigterm signal.
        """
        self.logging.info("Received shutdown signal.")
        self.stopped = True

    async def init(self):
        self.redisc = await aioredis.create_redis_pool(
            ('redis', 6379), db=0, encoding='utf-8')

    async def get_tasks(self):
        while (await self.redisc.llen('tasks')) < 50 and not self.stopped:
            await asyncio.sleep(0.5)
        if self.stopped:
            return
        tasks = []
        while task := await self.redisc.lpop('tasks'):
            tasks.append(task)
        return tasks

    def run(self):

        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.init())
        self.logging.info("Starting Match Worker..")
        while not self.stopped:
            tasks = loop.run_until_complete(self.get_tasks())
            if not tasks:
                continue
            processed_tasks = [task for task in [self.process_task(task) for task in tasks] if task]

            self.logging.info("Inserting %s Matches.", len(processed_tasks))
            self.session.bulk_save_objects(processed_tasks)
            self.session.commit()
        self.logging.info("Shutting down DB_Connector")

    def process_task(self, task):
        summoner = json.loads(task)

        summoner_db = self.session.query(Summoner).filter_by(puuid=summoner['puuid']).first()
        to_check = ['wins', 'losses', 'tier', 'rank', 'leaguePoints', 'summonerName']
        if summoner_db and not all([summoner[key] == getattr(summoner_db, key) for key in to_check]):
            return

        series = None
        if "miniSeries" in summoner:
            series = summoner['miniSeries']['progress'][:-1]
        db_entry = Summoner(
            summonerId=summoner['summonerId'],
            accountId=summoner['accountId'],
            puuid=summoner['puuid'],
            summonerName=summoner['summonerName'],
            tier=Tier.get(summoner['tier']),
            rank=Rank.get(summoner['rank']),
            leaguePoints=summoner['leaguePoints'],
            series=series,
            server=Server.get(self.server),
            wins=summoner['wins'],
            losses=summoner['losses'])
        return db_entry
