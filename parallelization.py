from threading import Thread, Lock
import logging
import time
import os
from random import randrange
import common_tools as ctools
from queue import Queue

MAX_NUMBER_OF_THREADS = os.cpu_count() + 1

class StudyThread(Thread):
    number_of_inst_processed: int = 1
    number_of_st_processed: int = 1
    number_of_all_studies: int = 1
    number_of_all_instances: int = 1
    instance_counter_lock = Lock()
    start_time = time.time()

    def __init__(self, queue: Queue, **kwarg):
        Thread.__init__(self, **kwarg)
        self._queue = queue

    def run(self): 
        logger = logging.getLogger(__name__)
        while True:
            (study_processor, args) = self._queue.get()
            logger.info('Start fixing study({}) out of {}'.format(
                StudyThread.number_of_st_processed, 
                StudyThread.number_of_all_studies,))
            study_uid = args[1][0]
            try:
                instances = study_processor(*args)
                with StudyThread.instance_counter_lock:
                    StudyThread.number_of_inst_processed += instances
                    StudyThread.number_of_st_processed += 1
            except BaseException as err:
                logger.error(err, exc_info=True)

            progress = float(StudyThread.number_of_inst_processed) /\
                float(StudyThread.number_of_all_inst)
            time_point = time.time()
            time_elapsed = round(time_point - StudyThread.start_time)
            time_left = round(
                StudyThread.number_of_all_instances -
                StudyThread.number_of_inst_processed
                ) * time_elapsed / float(StudyThread.number_of_inst_processed)
            header = '{}/{})Study {} was fix/convert-ed successfully'.format(
                StudyThread.number_of_st_processed, 
                StudyThread.number_of_all_studies, study_uid)
            progress_string = ctools.ShowProgress(
                progress, time_elapsed, time_left, 60, header, False)
            logger.info(progress_string)
            self._queue.task_done()


class WorkerThread(Thread):

    def __init__(self, queue: Queue, **kwarg):
        Thread.__init__(self, **kwarg)
        self.output = []
        self._queue = queue
        self._kill = False
        self._lock = Lock()

    def run(self):
        logger = logging.getLogger(__name__)
        time_interval_for_log = 30 * 20
        tic = time.time() - randrange(0, time_interval_for_log)
        while not self._kill:
            toc = time.time()
            if (toc - tic) > time_interval_for_log:
                tic = toc
                logger.info(
                    "new task out of {} in queue".format(self._queue.qsize()+1))
            (work_fun, args) = self._queue.get()
            if work_fun is None or args is None:
                continue
            try:
                out = work_fun(*args)
                with self._lock:
                    self.output.append(out)
                # logger.info('this is the out ({}, {}, {}, {}) all outputs: ({})'.format(
                #     len(out[0]),
                #     len(out[1]),
                #     len(out[2]),
                #     len(out[3]),
                #     len(self.output)))
            except BaseException as err:
                logger.error(err, exc_info=True)

            self._queue.task_done()

    def kill(self):
        self._kill = True


class ThreadPool:
    def __init__(self, max_number_of_threads: int,
                 thread_name_prifix: str = ''):
        self._queue = Queue()
        self._thread_pool = []
        self.output = []
        self._lock = Lock()
        for i in range(max_number_of_threads):
            self._thread_pool.append(self._create_th(
                '{}{:02d}'.format(thread_name_prifix, i)
            ))

    def _create_th(self, th_name) -> WorkerThread:
        t = WorkerThread(self._queue, name=th_name)
        t.daemon = True
        t.start()
        return t

    @property
    def queue(self):
        return self._queue

    def kill_them_all(self):
        logger = logging.getLogger(__name__)
        logger.info('killing all threads')
        for t in self._thread_pool:
            t.kill()
        for t in self._thread_pool:
            # I'm putting none to push queue out of block
            self._queue.put((None, None))
        for t in self._thread_pool:
            t.join()
        logger.info('collecting all output data from threads')
        for t in self._thread_pool:
            self.output.extend(t.output)  
        logger.info('threads all finished')