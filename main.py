#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import glob
import math
import getopt
import requests
import re
from tqdm import tqdm, trange
from config import *
from user import User


#TODO: I should do a function that his only purpose is to request and return data
def book_request(user, offset=0, limit=10, verbose=False):
    data = []
    url = BASE_URL + PRODUCTS_ENDPOINT.format(offset=offset, limit=limit)
    if verbose:
        print(url)
    r = requests.get(url, headers=user.get_header())
    data += r.json().get('data', [])

    return url, r, data

def get_all_books(user, offset=0, limit=10, is_verbose=False, is_quiet=False):
    '''
        Request all your books, return json with info of all your books
        Params
        ...
        header : str
        offset : int
        limit : int
            how many book wanna get by request
    '''
    # TODO: given x time jwt expired and should refresh the header, user.refresh_header()

    url, r, data = book_request(user, offset, limit)

    print(f'You have {str(r.json()["count"])} books')
    print("Getting list of books...")

    if not is_quiet:
        pages_list = trange(r.json()['count'] // limit, unit='Pages')
    else:
        pages_list = range(r.json()['count'] // limit)
    for i in pages_list:
        offset += limit
        data += book_request(user, offset, limit, is_verbose)[2]
    return data


def get_books(user, ids=[], is_verbose=False, is_quiet=False):
    '''
        Request specified books, return json with info of specified books
        Params
        ...
        header : str
        ids : int
            how many book wanna get by request
    '''

    print(f'You have requested {len(ids)} book(s)')
    print("Getting list of book(s)...")

    data = []
    for id in ids:
        url = BASE_URL + URL_BOOK_DETAIL_ENDPOINT.format(book_id=id)
        r = requests.get(url, headers=user.get_header())
        if r.status_code == 200: # success
            r_data = r.json().get('data','')
            r_data['productName'] = r_data['title']
            data.append(r_data)
    return data


def get_url_book(user, book_id, format='pdf', is_verbose=False):
    '''
        Return url of the book to download
    '''

    url = BASE_URL + URL_BOOK_ENDPOINT.format(book_id=book_id, format=format)
    r = requests.get(url, headers=user.get_header())

    if r.status_code == 200: # success
        return r.json().get('data', '')

    elif r.status_code == 401: # jwt expired
        user.refresh_header() # refresh token
        return get_url_book(user, book_id, format)  # call recursive

    elif r.status_code == 403: # do not own; try subscription
        if is_verbose:
            tqdm.write(f'{book_id} is not owned, trying subscription')
        return get_url_sections(user, book_id, is_verbose=is_verbose)  # call recursive

    print('ERROR (please copy and paste in the issue)')
    print(r.json())
    print(r.status_code)
    return []


def get_url_sections(user, book_id, is_verbose=False):
    '''
        Return url of the sections to download
    '''

    tqdm.write('Fetching chapters & sections...')
    url = URL_BOOK_TOC_ENDPOINT.format(book_id=book_id)
    r = requests.get(url)

    section_urls = []
    chapters = r.json().get('chapters', '')
    for c in tqdm(chapters, unit='Chapter'):
        for s in tqdm(c['sections'], unit='Section'):
            surl = BASE_URL + URL_BOOK_SECTION_ENDPOINT.format(book_id=book_id, chapter_id=c['id'], section_id=s['id'])
            r = requests.get(surl, headers=user.get_header())
            section_urls.append(r.json().get('data', ''))
    if is_verbose:
        tqdm.write(f'{book_id} has {len(section_urls)} sections in {len(chapters)} chapters')
    return section_urls


def get_book_file_types(user, book_id):
    '''
        Return a list with file types of a book
    '''

    url = BASE_URL + URL_BOOK_TYPES_ENDPOINT.format(book_id=book_id)
    r = requests.get(url, headers=user.get_header())

    if  (r.status_code == 200): # success
        return r.json()['data'][0].get('fileTypes', [])

    elif (r.status_code == 401): # jwt expired
        user.refresh_header() # refresh token
        return get_book_file_types(user, book_id, format)  # call recursive

    print('ERROR (please copy and paste in the issue)')
    print(r.json())
    print(r.status_code)
    return []


# TODO: i'd like that this functions be async and download faster
def download_book(filename, url):
    '''
        Download your book
    '''
    tqdm.write('Starting to download ' + filename)

    with open(filename, 'wb') as f:
        r = requests.get(url, stream=True)
        total = r.headers.get('content-length')
        if total is None:
            f.write(r.content)
        else:
            total = int(total)
            # TODO: read more about tqdm
            with tqdm(total=total, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()
                        pbar.update(len(chunk))
            tqdm.write('Finished ' + filename)


def make_zip(filename):
    if filename[-5:] == '.code':
        os.replace(filename, filename[:-5] + '_Code.zip')
    if filename[-6:] == '.video':
        os.replace(filename, filename[:-6] + '.zip')


def move_current_files(root, book):
    sub_dir = f'{root}/{book}'
    does_dir_exist(sub_dir)
    for f in glob.iglob(sub_dir + '.*'):
        try:
            os.rename(f, f'{sub_dir}/{book}' + f[f.index('.'):])
        except OSError:
            os.rename(f, f'{sub_dir}/{book}' + '_1' + f[f.index('.'):])
        except ValueError as e:
            print(e)
            print('Skipping')


def does_dir_exist(directory):
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except Exception as e:
            print(e)
            sys.exit(2)


def main(argv):
    # thanks to https://github.com/ozzieperez/packtpub-library-downloader/blob/master/downloader.py
    email = None
    password = None
    root_directory = 'media'
    book_file_types = ['pdf', 'mobi', 'epub', 'code', 'video']
    all_books = True
    book_ids = []
    separate = None
    verbose = None
    quiet = None
    errorMessage = 'Usage: main.py [-e <email> -p <password> -d <directory> -t <book file types> -b <book ids> -s -v -q]'

    # get the command line arguments/options
    try:
        opts, args = getopt.getopt(
            argv, 'e:p:d:b:t:svq', ['email=', 'pass=', 'directory=', 'books=', 'types=',  'separate', 'verbose', 'quiet'])
    except getopt.GetoptError:
        print(errorMessage)
        sys.exit(2)

    # hold the values of the command line options
    for opt, arg in opts:
        if opt in ('-e', '--email'):
            email = arg
        elif opt in ('-p', '--pass'):
            password = arg
        elif opt in ('-d', '--directory'):
            root_directory = os.path.expanduser(
                arg) if '~' in arg else os.path.abspath(arg)
        elif opt in ('-t', '--types'):
            book_file_types = arg.split(',')
        elif opt in ('-b', '--books'):
            book_ids = arg.split(',')
            all_books = False
        elif opt in ('-s', '--separate'):
            separate = True
        elif opt in ('-v', '--verbose'):
            verbose = True
        elif opt in ('-q', '--quiet'):
            quiet = True

    if verbose and quiet:
        print("Verbose and quiet cannot be used together.")
        sys.exit(2)

    # do we have the minimum required info?
    if (not email or not password)  and (not os.path.exists('token.json')):
        print(errorMessage)
        sys.exit(2)

    # check if not exists dir and create
    does_dir_exist(root_directory)

    # create user with his properly header
    if email and password:
        user = User(**{'username': email, 'password': password, 'file': True})
    else:
        user =  User()

    # get all your books
    if all_books:
        books = get_all_books(user, is_verbose=verbose, is_quiet=quiet)
    else:
        books = get_books(user,ids=book_ids, is_verbose=verbose, is_quiet=quiet)
    print('Downloading books...')
    if not quiet:
        books_iter = tqdm(books, unit='Book')
    else:
        books_iter = books

    search_path = f'{root_directory}/*/*' if separate else f'{root_directory}/*'
    downloaded_files = [ f for f in glob.glob(search_path, recursive=True) ]

    for book in books_iter:
        # get the different file type of current book
        file_types = get_book_file_types(user, book['productId'])
        book_name = book['productName'].replace(' ', '_').replace('.', '_').replace(':', '_').replace('/','')
        #move_current_files(root_directory, book_name)
        does_dir_exist(f'{root_directory}/{book_name}')
        for file_type in file_types:
            if file_type in book_file_types:  # check if the file type entered is available by the current book
                if separate:
                    filename = f'{root_directory}/{book_name}/{book_name}.{file_type}'
                else:
                    filename = f'{root_directory}/{book_name}.{file_type}'
                # get url of the book to download
                url = get_url_book(user, book['productId'], format=file_type, is_verbose=verbose)
                if isinstance(url, list):
                    if not quiet:
                        url_iter = tqdm(url, unit='Section')
                    else:
                        url_iter = url
                    for u in url_iter:
                        d = '/'.join(filename.split('/')[:-1])
                        f = u.split('/')[-1].split('?')[0]
                        filename = f'{d}/{f}'
                        if not filename in downloaded_files:
                            download_book(filename, u)
                        else:
                            if verbose:
                                tqdm.write(f'{filename} already exists, skipping.')

                else:
                    if not filename in downloaded_files \
                            and not re.sub('.code$', '_Code.zip', filename) in downloaded_files \
                            and not re.sub('.video$', '.zip', filename) in downloaded_files:
                        download_book(filename, url)
                        make_zip(filename)
                    else:
                        if verbose:
                            tqdm.write(f'{filename} already exists, skipping.')


if __name__ == '__main__':
    main(sys.argv[1:])
    print('All complete...!')
# -*- coding: utf-8 -*-
