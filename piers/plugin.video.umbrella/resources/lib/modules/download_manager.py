"""Persistent download status shared by separate Kodi plugin invocations.

Stores display metadata only; resolved URLs and request headers never enter
the history database. Home-window markers identify workers in this Kodi run.
"""
import os
import sqlite3
from contextlib import closing
from time import time
from uuid import uuid4

ACTIVE = ('Connecting', 'Awaiting confirmation', 'Downloading', 'Retrying', 'Cancelling')


class DownloadStore:
    def __init__(self, path=None, window=None):
        from resources.lib.modules import control
        self.path = path or os.path.join(control.dataPath, 'downloads.db')
        self.window = window if window is not None else control.homeWindow
        if not path: control.makeFile(control.dataPath)
        with closing(self.connect()) as con, con:
            con.execute('''CREATE TABLE IF NOT EXISTS downloads (
                id TEXT PRIMARY KEY, title TEXT, destination TEXT, status TEXT,
                downloaded INTEGER, total INTEGER, speed REAL, message TEXT,
                created REAL, updated REAL, cancel INTEGER DEFAULT 0)''')

    def connect(self):
        con = sqlite3.connect(self.path, timeout=5)
        con.row_factory = sqlite3.Row
        return con

    def marker(self, job):
        return 'umbrella.download.' + job

    def create(self, title, destination):
        job = uuid4().hex
        self.window.setProperty(self.marker(job), 'running')
        try:
            with closing(self.connect()) as con, con:
                con.execute('BEGIN IMMEDIATE')
                rows = con.execute('SELECT id, status FROM downloads WHERE destination=?', (destination,)).fetchall()
                for row in rows:
                    if row['status'] in ACTIVE and self.window.getProperty(self.marker(row['id'])):
                        raise ValueError('This file is already being downloaded.')
                now = time()
                con.execute('INSERT INTO downloads VALUES (?, ?, ?, ?, 0, 0, 0, ?, ?, ?, 0)',
                            (job, title, destination, 'Connecting', '', now, now))
            return job
        except Exception:
            self.window.clearProperty(self.marker(job))
            raise

    def update(self, job, status, downloaded=0, total=0, speed=0, message=''):
        with closing(self.connect()) as con, con:
            con.execute('UPDATE downloads SET status=?, downloaded=?, total=?, speed=?, message=?, updated=? WHERE id=?',
                        (status, downloaded, total, speed, message, time(), job))
        if status not in ACTIVE: self.window.clearProperty(self.marker(job))

    def cancelled(self, job):
        with closing(self.connect()) as con:
            row = con.execute('SELECT cancel FROM downloads WHERE id=?', (job,)).fetchone()
        return bool(row and row['cancel'])

    def cancel(self, job):
        with closing(self.connect()) as con, con:
            con.execute("UPDATE downloads SET cancel=1, status='Cancelling' WHERE id=? AND status IN (%s)" %
                        ','.join('?' for _ in ACTIVE), (job,) + ACTIVE)

    def rows(self):
        with closing(self.connect()) as con, con:
            rows = con.execute('SELECT * FROM downloads ORDER BY created DESC').fetchall()
            for row in rows:
                if row['status'] in ACTIVE and not self.window.getProperty(self.marker(row['id'])):
                    con.execute("UPDATE downloads SET status='Interrupted', message=? WHERE id=?",
                                ('Kodi or the download worker stopped before completion.', row['id']))
            return [dict(row) for row in con.execute('''SELECT * FROM downloads
                ORDER BY CASE WHEN status IN ('Connecting','Awaiting confirmation','Downloading','Retrying','Cancelling')
                THEN 0 ELSE 1 END, created DESC LIMIT 200''')]

    def remove(self, job):
        """Remove a finished history entry without touching its files."""
        with closing(self.connect()) as con, con:
            result = con.execute('''DELETE FROM downloads WHERE id=?
                AND status IN ('Failed', 'Cancelled', 'Interrupted', 'Completed')''', (job,))
            return result.rowcount > 0


def open_manager():
    from resources.lib.modules import control
    from resources.lib.windows.download_manager import DownloadManager
    try:
        store = DownloadStore()
        window = DownloadManager('download_manager.xml', control.addonInfo('path'), 'Default', '1080i', store=store)
        window.run()
        del window
    except Exception:
        control.notification(title='Downloads', message='Unable to open download history.', icon='ERROR')
