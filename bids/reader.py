from base.dataset import DataSet
from base.subject import Subject
from base.image import Image, FunctionalImage
from base.group import Group, FunctionalGroup
from base.session import Session
import glob
import os
import re
import csv
import codecs


class Reader(object):
    def load_data_set(self, path_to_data_set):
        return DataSet(self.get_subject_subjects(path_to_data_set))

    def get_subject_subjects(self, path_to_data_set):
        return [read_subject(path_to_subject) for path_to_subject in self.find_subject_folders(path_to_data_set)]

    def find_subject_folders(self, path_to_data_set):
        return sorted(glob.glob(os.path.join(path_to_data_set, "sub-*")))


class SubjectReader(object):
    def read_subject(self, path_to_subject):
        subject_id = self.parse_subject_id(path_to_subject)
        subject = Subject(subject_id)
        session_folders = glob.glob(os.path.join(path_to_subject, "ses-*"))
        contains_sessions = any(["ses-" == os.path.basename(folder)[:4] for folder in session_folders])
        if contains_sessions:
            for session_folder in session_folders:
                session = read_session(session_folder)
                subject.add_session(session)
        else:
            session = read_session(path_to_subject)
            subject.add_session(session)
        return subject

    def parse_subject_id(self, path_to_subject):
        return os.path.basename(path_to_subject).lstrip("sub-")


class SessionReader(object):
    def read_session(self, path_to_session_folder):
        session_name = self.parse_session_name(path_to_session_folder)
        session = Session(name=session_name, path=path_to_session_folder)
        for group in self.load_groups(path_to_session_folder):
            session.add_group(group)
        return session

    def parse_session_name(self, path_to_session_folder):
        return os.path.basename(path_to_session_folder).lstrip("ses-")

    def load_groups(self, path_to_session_folder):
        return [read_group(group_folder) for group_folder in glob.glob(os.path.join(path_to_session_folder, "*"))]


class GroupReader(object):
    def load_group(self, path_to_group_folder):
        group_name = self.parse_group_name(path_to_group_folder)
        images = self.read_images(path_to_group_folder)
        if group_name == "func":
            return FunctionalGroup(name=group_name, images=images, path=path_to_group_folder)
        else:
            return Group(name=group_name, images=images, path=path_to_group_folder)

    def parse_group_name(self, path_to_group_folder):
        return os.path.basename(path_to_group_folder)

    def read_images(self, path_to_group_folder):
        return [read_image(image_file) for image_file in glob.glob(os.path.join(path_to_group_folder, "*.nii*"))]


class ImageReader(object):
    def read_image_from_bids_path(self, path_to_image):
        modality = self.parse_image_modality(path_to_image)
        acquisition = self.parse_generic_name(path_to_image, name="acq")
        task_name = self.parse_task_name(path_to_image)
        return self.read_image(path_to_image, modality=modality, acquisition=acquisition, task_name=task_name)

    @staticmethod
    def read_image(path_to_image, modality=None, acquisition=None, task_name=None):
        if modality == "bold":
            return FunctionalImage(modality=modality,
                                   file_path=path_to_image,
                                   acquisition=acquisition,
                                   task_name=task_name)
        else:
            return Image(modality=modality, file_path=path_to_image, acquisition=acquisition)

    @staticmethod
    def parse_image_modality(path_to_image):
        return os.path.basename(path_to_image).split(".")[0].split("_")[-1]

    @staticmethod
    def parse_generic_name(path_to_image, name):
        result = re.search('(?<={name}-)[a-z0-9]*'.format(name=name), os.path.basename(path_to_image))
        if result:
            return result.group(0)

    def parse_task_name(self, path_to_image):
        return self.parse_generic_name(path_to_image, name="task")


def read_subject(path_to_subject_folder):
    return SubjectReader().read_subject(path_to_subject_folder)


def read_group(path_to_group_folder):
    return GroupReader().load_group(path_to_group_folder)


def read_session(path_to_session_folder):
    return SessionReader().read_session(path_to_session_folder)


def read_image(path_to_image_file):
    return ImageReader().read_image_from_bids_path(path_to_image_file)


def read_dataset(path_to_dataset_folder):
    return Reader().load_data_set(path_to_dataset_folder)


def read_csv(path_to_csv_file):
    return CSVReader(path_to_csv_file).read_csv()


class CSVReader(object):
    def __init__(self, path_to_csv_file):
        self.dataset = DataSet()
        self.path_to_csv_file = os.path.abspath(path_to_csv_file)
        self._directory = os.path.dirname(self.path_to_csv_file)

    def read_csv(self):
        with codecs.open(self.path_to_csv_file, "rU", "utf-16") as csv_file:
            reader = csv.DictReader(csv_file)
            for line in reader:
                subject_id = line["subject"]

                if not self.dataset.has_subject_id(subject_id):
                    subject = Subject(subject_id=subject_id)
                    self.dataset.add_subject(subject)
                else:
                    subject = self.dataset.get_subject(subject_id)

                session_name = line["session"]
                if not subject.has_session(session_name):
                    session = Session(name=session_name)
                    subject.add_session(session)
                else:
                    session = subject.get_session(session_name)

                image = self.read_image(line["file"], line["modality"], line['task'])
                group_name = self.modality_to_group_name(image.get_modality())

                if session.has_group(group_name):
                    group = session.get_group(group_name)
                else:
                    group = Group(name=group_name)
                    session.add_group(group)

                group.add_image(image)

        return self.dataset

    def read_image(self, file_path, modality, task_name=None):
        modality = self.correct_modality(modality.lower())
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(os.path.join(self._directory, file_path))
        return ImageReader.read_image(path_to_image=file_path, modality=modality, task_name=task_name)

    @staticmethod
    def correct_modality(modality):
        if "t1" in modality:
            return 'T1w'
        elif "flair" in modality:
            return 'FLAIR'
        return modality

    @staticmethod
    def modality_to_group_name(modality):
        if "bold" in modality.lower():
            return "func"
        return "anat"
