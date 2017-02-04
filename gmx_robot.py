# coding=utf-8
"""
GMX EMAIL AUTOREG ROBOT

DATA REQUIRED:
    reg_url        https://registrierung.gmx.net/
    ip             123.123.123.123
    gender         male || female
    name           male_name_db || female_name_db
    surname        surname db
    country        Germany || Austria || Switzerland
    city           Frankfurt am Main, related to IP
    zip            90943, related to city
    street         Street Name, related to zip
    house          1, related to street
    birthday       17.03.1984
    email          name+surname+birthyear || name+surname || reverse
    password       8-40 characters
    contact_email  can be blank
    phone          can be blank
    secret         maiden name, from female_name_db
    captcha        rucaptcha or selfsolve with gui

MISC:
    for socks proxy to work with requests module on win:
        pip install -U requests[socks]
        pip install pysocks
        pip install win_inet_pton
        import socks
"""

import os
import random
import socks  # this should stay for socks to work
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from PIL import Image, ImageTk
import Tkinter as Tk
import tkFont
from StringIO import StringIO
import re
import requests
import base64
import time
import subprocess


class RuCaptcha(object):
    """
    rucaptcha api wrapper
    """

    def __init__(self, api_key):
        self.key = api_key
        self.sleep = 3
        self.user_agent = {'User-Agent': 'rucaptcha'}
        self.solvetime = int(self.get_stats()[3])

    def post(self, img):
        """
        :param img: should be base64 str or file path to .png .gif .jpg
        :return response object
        """
        capt_id = ''

        ext = ['.png', 'gif', '.jpg', ]
        if img.endswith(tuple(ext)):
            with open(img, 'rb') as f:
                img = base64.b64encode(f.read())

        url = 'http://rucaptcha.com/in.php'
        h = {'User-Agent': 'rucaptcha'}
        d = {'key': self.key,
             'method': 'base64',
             'body': img,
             'regsense': 1,
             'numeric': 4,
             'language': 2}
        res = requests.post(url, headers=h, data=d)

        print res.content
        if res.content.startswith('OK'):
            capt_id = res.content.split('|')[1].lower()

        return capt_id

    def get(self, capt_id):
        """
        recursive get until solve is ready
        """
        url = 'http://rucaptcha.com/res.php'
        h = self.user_agent
        d = {'key': self.key, 'action': 'get', 'id': capt_id}

        time.sleep(self.solvetime) if self.sleep == 3 else time.sleep(1)
        res = requests.get(url, headers=h, params=d)
        print res.content
        if res.content.startswith('OK'):
            captcha = res.content.split('|')[1]
            return captcha
        elif res.content.startswith('CAPCHA_NOT_READY'):
            # sleep for 3 sec first, then for 1 sec
            time.sleep(self.sleep)
            self.sleep = 1
            return self.get(capt_id)
        else:
            code = res.status_code
            content = res.content
            raise Exception('%s %s' % code, content)

    def snitch(self, capt_id):
        """ report failed captcha """
        url = 'http://rucaptcha.com/res.php'
        h = self.user_agent
        d = {'key': self.key, 'action': 'reportbad', 'id': capt_id}
        res = requests.get(url, headers=h, params=d)
        print res.content
        return res

    def get_stats(self):
        """
        :return list of floats
        0 - workers waiting ie 50.0
        1 - workers load ie 100.0
        2 - minbid in rub ie 0.044 for 44 rub
        3 - avg gecognition time ie 12.0
        """
        url = 'http://rucaptcha.com/load.php'
        h = self.user_agent
        res = requests.get(url, headers=h)

        # clean response tags, etc
        rgx = re.compile(r'<.*?>')
        l = []
        for el in rgx.split(res.content):
            try:
                l.append(float(el))
            except ValueError:
                pass
        assert len(l) == 4
        return l


class CaptchaGui(object):
    """
    spawn a window with captcha image for quick self entry
    :param captcha: <path to image> or <PIL.Image.Image class>
    """

    def __init__(self, captcha):
        self.master = Tk.Tk()
        self.canvas = Tk.Canvas(self.master, width=220, height=50)
        self.entry = Tk.Entry(self.master)
        self.button = Tk.Button(self.master, text='Enter',
                                command=self.save_and_quit)

        if isinstance(captcha, Image.Image):
            self.captcha = ImageTk.PhotoImage(captcha)
        else:
            self.captcha = ImageTk.PhotoImage(Image.open(captcha))
        self.font = tkFont.Font(size=16)
        self.result = ''

        self.uinit()

    def run(self):
        self.master.lift()
        self.master.attributes('-topmost', True)
        self.master.attributes('-topmost', False)
        self.master.focus_force()
        self.master.mainloop()

    def uinit(self):
        self.master.minsize(width=220, height=100)
        self.master.maxsize(width=220, height=400)
        self.master.title('solve captcha')
        self.master.bind('<Return>', self.save_and_quit)

        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.captcha, anchor='nw')

        self.entry.pack(fill='both', expand='yes')
        self.entry.focus_set()
        self.entry['font'] = self.font

        self.button.pack(fill='both', expand='yes')
        self.button['font'] = self.font

    def save_and_quit(self, *args):
        self.result = self.entry.get()
        self.master.destroy()


class Misstake(object):
    """
    WIP
    make mistakes in strings ie 'f' -> 'ff', 'a' -> 'o'
    """

    # todo: other mistakes
    # todo: method to make random mistakes without spec
    # todo: plug into GmxRobot

    def __init__(self, string):
        self.string = string

    @staticmethod
    def find_indexes_patrn(stri, patrn):
        """
        find occurences of pattern in string
        return list of index tuples (start, end)
        """
        l = [(match.start(0), match.end(0))
             for match in re.finditer(patrn, stri)]
        return l

    @staticmethod
    def find_indexes_char(stri, char):
        """
        find occurences of single char in string
        return list of indexes
        """
        l = [indx for indx, letr in enumerate(stri) if letr == char]
        return l

    def miss_spell(self, a, b):
        """
        misspell one random occurence of 'a' for 'b'
        if no occurence is found -> return original string
        """

        strlist = list(self.string)

        if len(a) == 1:
            indexes = self.find_indexes_char(self.string, a)
            if indexes:
                choice = random.choice(indexes)
                strlist[choice] = b
        elif len(a) > 1:
            indexes = self.find_indexes_patrn(self.string, a)
            if indexes:
                start, end = random.choice(indexes)
                strlist[start:end] = b

        return "".join(strlist)


class EmailPermutator(object):
    """
    generate random email name
    + unicode umlaut support

    :param date: 'day.mon.year' ie '01.01.1000"
    """

    def __init__(self, name, surname, date):
        self.name = name.lower().replace(' ', '')
        self.surname = surname.lower().replace(' ', '')
        self.date = date.split('.')
        self.result = self.weld()

    @staticmethod
    def cut(str_to_cut):
        """ cut string by random len. result >= 1 """
        min_cut = 1
        max_cut = len(str_to_cut) - 1
        cut_by = random.randint(min_cut, max_cut)
        return cut_by

    @staticmethod
    def replace_uni(str_to_strip):
        """ replace umlauts with english """
        table = {
            ord(u'ä'): u'ae',
            ord(u'ö'): u'oe',
            ord(u'ü'): u'ue',
            ord(u'ß'): u'ss',
            ord(u'é'): u'e',
        }
        return str_to_strip.translate(table)

    @staticmethod
    def remove_random_vowels(str_to_remove):
        """ remove vowels a,e,i,o,u from string """
        vowels = 'aeiou'
        filtered = ''
        for char in str_to_remove:
            remove = random.randint(0, 1)
            if char in vowels:
                if remove:
                    pass
                else:
                    filtered += char
            else:
                filtered += char

        return filtered

    def stylize(self, string):
        """ return random variant of string """
        # todo: choice should be weighted towards full name and surname
        string = self.replace_uni(string)
        choice = random.randint(1, 3)

        if choice == 1:
            cut_by = self.cut(string)
            result = string[:-cut_by]
            return result
        elif choice == 2:
            return self.remove_random_vowels(string)
        elif choice == 3:
            return string

    @staticmethod
    def choose_pos(list_of_three):
        """
        :param list_of_three: [name, surname, salt]
        salt is either l[1] or l[2] but never l[0]
         """
        positions = [
            (0, 1, 2),  # name, surname, salt
            (0, 2, 1),
            (1, 0, 2),
            (1, 2, 0)
        ]
        choice = random.choice(positions)
        l = []
        for el in choice:
            l.append(list_of_three[el])
        return l

    def weld(self):
        """
        weld variants of name, surname, year together + some salt
        randomly place one dot after 1st or 2nd el, but not both
        shuffle name, surname, date positions
        """
        name = self.stylize(self.name)
        surname = self.stylize(self.surname)
        salt = random.choice(self.date)

        l = self.choose_pos([name, surname, salt])

        result = []
        dot_placed = False
        for el in l[0:2]:
            if not dot_placed:
                place_dot = random.randint(0, 1)
                if place_dot:
                    el += '.'
                    result.append(el)
                    dot_placed = True
                else:
                    result.append(el)
            else:
                result.append(el)
        result.append(l[2])

        return ''.join(result)


class ConfigParser(object):
    """
    parse config file line by line
    store configuration
    """

    def __init__(self, config_file):
        self.config_file = config_file

        self.reg_url = ''
        self.mnames_file = ''
        self.fnames_file = ''
        self.surnames_file = ''
        self.location_file = ''
        self.data_file = ''
        self.rucapt_apikey = ''
        self.firefox_exe = ''
        self.gecko_path = ''
        self.ssh_exe = ''
        self.ssh_usr = ''
        self.ssh_port = ''
        self.proxy_file = ''

        self.parse_config()

    @staticmethod
    def parse_line(line):
        """
        line syntax
            comment:   # comment
            option:    param_name "param_option"
        """
        return line.split('"')[-2]

    def parse_config(self):
        with open(self.config_file, 'r') as config:
            for line in config:
                line = line.strip()
                if line.startswith('#'):
                    continue
                elif line.startswith('regurl'):
                    self.reg_url = self.parse_line(line)
                elif line.startswith('mnames'):
                    self.mnames_file = self.parse_line(line)
                elif line.startswith('fnames'):
                    self.fnames_file = self.parse_line(line)
                elif line.startswith('surnames'):
                    self.surnames_file = self.parse_line(line)
                elif line.startswith('location'):
                    self.location_file = self.parse_line(line)
                elif line.startswith('data'):
                    self.data_file = self.parse_line(line)
                elif line.startswith('rucapt'):
                    self.rucapt_apikey = self.parse_line(line)
                elif line.startswith('firefox'):
                    self.firefox_exe = self.parse_line(line)
                elif line.startswith('gecko'):
                    self.gecko_path = self.parse_line(line)
                elif line.startswith('ssh_exe'):
                    self.ssh_exe = self.parse_line(line)
                elif line.startswith('ssh_usr'):
                    self.ssh_usr = self.parse_line(line)
                elif line.startswith('ssh_port'):
                    self.ssh_port = self.parse_line(line)
                elif line.startswith('proxy'):
                    self.proxy_file = self.parse_line(line)
                else:
                    pass


class DataInit(object):
    """
    This class is used to kickstart and hold data
    required in gmx email fields

    1. parse data files:

        location.txt
        names_f.txt
        names_m.txt
        surnames.txt

    choose random data from parsed file and store:
        name, surname, country, city, street,
        zipcode, secret

    2. generate and store additional misc data:
        birthday, house, gender

    :param proxy: (str) 'host:port'
    """

    def __init__(self, config, proxy):
        self.conf = config
        self.proxy = proxy
        self.password = Password(12, 15).result
        self.gender = random.choice(['M', 'F'])
        self.ip = self.set_ip()
        self.name = self.set_mname() if self.gender == 'M' else self.set_fname()
        self.surname = self.set_surname()
        self.country = self.set_location()[0]
        self.city = self.set_location()[1]
        self.street = self.set_location()[2]
        self.zipcode = self.set_location()[3]
        self.house = str(random.randint(1, 15))  # wild guess
        self.secret = self.set_secret()
        self.bday = self.set_birthday()[0]
        self.bmonth = self.set_birthday()[1]
        self.byear = self.set_birthday()[2]
        self.birthday = self.set_birthday()[3]
        self.email = self.set_email()  # this should come last

    def __str__(self):
        """
        print state of data for debug
        """
        l = [
            'gender:   ' + self.gender,
            'name:     ' + self.name,
            'surname:  ' + self.surname,
            'country:  ' + self.country,
            'city:     ' + self.city,
            'street:   ' + self.street,
            'zip:      ' + self.zipcode,
            'house:    ' + self.house,
            'secret:   ' + self.secret,
            'birthday: ' + self.birthday,
            'email:    ' + self.email,
            'password: ' + self.password,
            'ip:       ' + self.ip,
        ]
        return '%s' % '\n'.join(l).encode('utf-8')

    def set_email(self):
        """ resets email each time it's called """
        email = EmailPermutator(self.name, self.surname,
                                self.birthday).result
        self.email = email  # this is needed when regenerating email
        return email

    @staticmethod
    def line_from_parsed(path_to_file):
        """
        read file into memory
        and return random element from list
        """
        with open(path_to_file, 'r') as infile:
            lines = []
            for line in infile:
                lines.append(line.decode('utf-8').strip())
        select_line = random.choice(lines)
        return select_line

    @staticmethod
    def set_birthday():
        day = "%02d" % random.randint(1, 29)
        month = "%02d" % random.randint(1, 12)
        year = str(random.randint(1970, 1999))
        birthday = "%s.%s.%4s" % (day, month, year)
        return [day, month, year, birthday]

    def set_location(self):
        """
        example input:
            Deutchland,Frankfurt am Main,Alte Mainzer Gasse,60311
        """
        data = self.line_from_parsed(self.conf.location_file).split(',')
        return data

    def set_fname(self):
        """ set female name """
        return self.line_from_parsed(self.conf.fnames_file)

    def set_mname(self):
        """ set male name """
        return self.line_from_parsed(self.conf.mnames_file)

    def set_surname(self):
        """ set surname """
        return self.line_from_parsed(self.conf.surnames_file)

    def set_secret(self):
        """ set secret """
        return self.line_from_parsed(self.conf.fnames_file)

    def set_ip(self):
        """
        set ip used during sing up
        """
        proxy_host, proxy_port = self.proxy.split(':')
        proxies = {
            'all': None,
            'https': 'socks5://%s:%s' % (proxy_host, proxy_port),
        }
        url = 'https://api.ipify.org'
        headers = {'User-Agent': 'ipify'}
        r = requests.get(url, headers=headers, proxies=proxies)
        assert r.status_code == 200
        return r.content


class Password(object):
    """
    generate password and store in self.result
    guides from gmx:
        use 12-15 characters
        mix numbers and letters
        blend uppercase and lowercase
        use special characters

    """

    def __init__(self, len_min, len_max):
        self.len_min = len_min
        self.len_max = len_max

        self.letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        self.digits = '0123456789'
        self.special = '#$%&()*+,-./:;<=>?@[\]^_{|}'

        self.result = self.generate()

    def generate(self):
        length = random.randint(self.len_min, self.len_max)
        result = ''
        for f in range(length):
            result += random.choice(self.letters + self.digits + self.special)
        return result


class FirefoxDriver(object):
    """
    setup working driver for Firefox
    :param proxy (str) socks5
    :param config (obj) ConfigParser
    """

    def __init__(self, config, proxy):
        self.proxy = proxy
        self.kill_all()
        self.fox_path = config.firefox_exe
        self.gecko_path = config.gecko_path
        self.check_gecko()
        self.fox_profile = webdriver.FirefoxProfile()
        self.fox_setup()
        self.driver = webdriver.Firefox(firefox_profile=self.fox_profile,
                                        firefox_binary=self.fox_path,
                                        log_path=os.devnull)
        self.driver.implicitly_wait(60)

    def check_gecko(self):
        """ for firefox to work, gecko must be in path """
        if 'Geckodriver' not in os.environ['PATH']:
            os.environ['PATH'] += os.pathsep + self.gecko_path

    @staticmethod
    def kill_all():
        """
        kill old processes if running
        """
        os.system('taskkill /F /IM geckodriver.exe')
        os.system('taskkill /F /IM plugin-container.exe')
        os.system('taskkill /F /IM firefox.exe')

    def fox_setup(self):
        """
        basic hardening + proxy
        """
        proxy_host, proxy_port = self.proxy.split(':')
        prefs = {
            'extensions.logging.enabled': False,
            'datareporting.healthreport.about.reportUrl': '',
            'datareporting.healthreport.infoURL': '',
            'datareporting.healthreport.logging.consoleEnabled': False,
            'datareporting.healthreport.service.enabled': False,
            'datareporting.healthreport.service.firstRun': False,
            'datareporting.healthreport.uploadEnabled': False,
            'datareporting.policy.dataSubmissionEnabled': False,
            'app.update.auto': False,
            'app.update.enabled': False,
            'browser.search.countryCode': 'US',
            'browser.search.region': 'US',
            'browser.search.update': False,
            'extensions.update.enabled': False,
            'media.peerconnection.enabled': False,
            'browser.selfsupport.url': '',
            'network.proxy.type': 1,
            'network.proxy.socks': proxy_host,
            'network.proxy.socks_port': int(proxy_port),
            'network.proxy.socks_remote_dns': True,
        }

        for k, val in prefs.items():
            self.fox_profile.set_preference(k, val)


class GmxRobot(object):
    """
    main class. sing up and save credentials to disk
    repetative methods are daisy chained for
    todo: should be able to swap FirefoxDriver with another (chrome, phantomjs)
    :param proxy (str) 'host:port'
    """

    def __init__(self, config, proxy):
        self.config = config
        self.data = DataInit(config, proxy)
        self.driver = FirefoxDriver(config, proxy).driver
        self.rucapt = RuCaptcha(config.rucapt_apikey)

        # id for currect captcha solve to report
        self.current_solve_id = ''

    def run(self):
        """
        main loop
        1. go to page
        2. get element handles
        3. enter data
        4. handle captcha
        5. register email
        6. save data
        """
        # go to reg page
        self.driver.get(self.config.reg_url)

        # get element handles,
        _female = self.driver.find_element_by_id('id4')
        _male = self.driver.find_element_by_id('id3')
        _name = self.driver.find_element_by_id('id1')
        _surname = self.driver.find_element_by_id('id2')
        _country_sel = self.driver.find_element_by_id('id34')
        _zip = self.driver.find_element_by_id('id6')
        _city = self.driver.find_element_by_id('id7')
        _street = self.driver.find_element_by_id('id8')
        _house = self.driver.find_element_by_id('id9')
        _birth_day = self.driver.find_element_by_id('ida')
        _birth_mon = self.driver.find_element_by_id('idb')
        _birth_yr = self.driver.find_element_by_id('idc')
        _email = self.driver.find_element_by_id('id35')
        _pwd = self.driver.find_element_by_id('id1f')
        _pwd2 = self.driver.find_element_by_id('id20')
        _secret_sel = self.driver.find_element_by_id('id38')
        _secret = self.driver.find_element_by_id('id24')
        _captcha = self.driver.find_element_by_id('id25')

        # enter data
        self.sleep(0.5, 1.5)
        if self.data.gender == 'M':
            self.click(_male).sleep(0.5, 1.5)
        else:
            self.click(_female).sleep(0.5, 1.5)
        self.send_keys_slow(_name, self.data.name).sleep(0.5, 1.5)
        self.send_keys_slow(_surname, self.data.surname).sleep(0.5, 1.5)
        self.select_opt(_country_sel, self.data.country).sleep(0.5, 1.5)
        self.send_keys_slow(_zip, self.data.zipcode).sleep(0.5, 1.5)
        self.send_keys_slow(_city, self.data.city).sleep(0.5, 1.5)
        self.send_keys_slow(_street, self.data.street).sleep(0.5, 1.5)
        self.send_keys_slow(_house, self.data.house).sleep(0.5, 1.5)
        self.send_keys_slow(_birth_day, self.data.bday).sleep(0.5, 1.5)
        self.send_keys_slow(_birth_mon, self.data.bmonth).sleep(0.5, 1.5)
        self.send_keys_slow(_birth_yr, self.data.byear).sleep(0.5, 1.5)
        self.send_keys_slow(_email, self.data.email).sleep(0.5, 1.5)
        self.check_email_valid().sleep(0.5, 1.5)
        self.scroll_into_view(_pwd).sleep(0.5, 1.5)
        self.send_keys_slow(_pwd, self.data.password).sleep(0.5, 1.5)
        self.send_keys_slow(_pwd2, self.data.password).sleep(0.5, 1.5)
        self.select_opt(_secret_sel, 'Geburtsname der Mutter').sleep(0.5, 1.5)
        self.send_keys_slow(_secret, self.data.secret).sleep(0.5, 1.5)

        # solve captcha
        capt_img = self.get_captcha_img()
        capt_text = self.solve_with_service(capt_img)
        self.send_keys_slow(_captcha, capt_text).sleep(0.5, 1.5)
        self.submit()
        self.sleep(5, 10)

        # sign up successfull, save data
        self.save_data()

        # post sign up tasks, scroll though popups
        _continue_btn = self.driver.find_element_by_id('weiterBtn')
        self.scroll_into_view(_continue_btn).sleep(0.5, 1.5)
        self.click(_continue_btn).sleep(5, 10)

        crnt_url = self.driver.current_url
        url_session = crnt_url.split('?')[1]  # can't visit url without params
        self.driver.get('https://navigator.gmx.net/mail?' + url_session)
        self.sleep(5, 10)

        os.system('taskkill /F /IM plugin-container.exe')
        self.driver.quit()

    def click(self, el):
        el.click()
        return self  # daisy chain

    def save_data(self):

        data = [
            'ip: ' + self.data.ip,
            'name: ' + self.data.name,
            'surname: ' + self.data.surname,
            'country: ' + self.data.country,
            'city: ' + self.data.city,
            'street: ' + self.data.street,
            'house: ' + self.data.house,
            'zip: ' + self.data.zipcode,
            'birthday: ' + self.data.birthday,
            'secret: ' + self.data.secret,
            'password: ' + self.data.password,
            'email: ' + self.data.email + '@gmx.de',
            '-----------------------------'
        ]

        with open(self.config.data_file, 'a') as infile:
            for line in data:
                infile.write((line + '\n').encode('utf-8'))

    def submit(self):
        """
        submit all data and register
        if captcha fails, restart
        """

        submit_btn = self.driver.find_element_by_id('submitButton')
        submit_btn.click()

        # err = 'feedbackPanelERROR'
        self.sleep(6.5, 9.5)
        if self.driver.current_url.startswith(self.config.reg_url):
            # report captcha
            self.rucapt.snitch(self.current_solve_id)
            self.current_solve_id = ''

            capt_img = self.get_captcha_img()
            capt_text = self.solve_with_service(capt_img)
            self.sleep(0.5, 1.5)
            captcha = self.driver.find_element_by_id('id25')
            self.send_keys_slow(captcha, capt_text).sleep(0.5, 1.5)
            self.submit()

    def get_captcha_img(self):
        """
        scroll captcha into view, save screenshot to memory as base64
        crop using PIL, save to disk as 'out.png'
        return PIL.Image.Image class + save image to disk with timestamp
        """

        captcha_refresh = self.driver.find_element_by_id('get_new_captcha')
        captcha_refresh.click()
        self.sleep(1.5, 2.5)
        captha_img = self.driver.find_element_by_css_selector('img.captcha')
        self.scroll_into_view(captha_img)
        loc = captha_img.location_once_scrolled_into_view
        size = captha_img.size

        screen64 = self.driver.get_screenshot_as_base64()
        screen64_decode = base64.decodestring(screen64)

        img = Image.open(StringIO(screen64_decode))
        left = loc['x']
        top = loc['y']
        right = loc['x'] + size['width']
        bottom = loc['y'] + size['height']

        img = img.crop((left, top, right, bottom))

        return img

    @staticmethod
    def solve_with_gui(img):
        """
        spawn quick gui popup for manual entry of captcha
        popup already has focus on entry field
        usage: enter captcha + press <Return>
        """
        captcha_gui = CaptchaGui(img)
        captcha_gui.run()
        return captcha_gui.result

    def solve_with_service(self, img):
        """
        :param img -> 'PIL.Image.Image' class

        todo: add 'base64' and 'file' as inputs
        todo: should be able to swap different services
        """
        buf = StringIO()
        img.save(buf, format='PNG')

        img64 = base64.b64encode(buf.getvalue())

        capt_id = self.rucapt.post(img64)
        solved = self.rucapt.get(capt_id)
        self.current_solve_id = capt_id

        # save solved captchas for audit later
        # .snitch() on the ones that solved incorrect
        img.save('./captcha/captcha%s_%s.png' % (capt_id, solved))

        return solved.lower()

    def check_email_valid(self):
        """
        check if email is valid, if not - generate new email name
        call this function recursively until valid name is found
        ! .make_email() updates email state in .data
        """
        btn = 'checkAvailabilityBtn'
        err = 'feedbackPanelERROR'

        chk_btn = self.driver.find_element_by_id(btn)
        chk_btn.click()
        self.sleep(6.5, 9.5)

        # previous email_input handle is stale at this point
        email_input = self.driver.find_element_by_id('id35')
        if err in email_input.get_attribute('class'):
            new_email = self.data.set_email()
            email_input.clear()
            self.sleep(0.5, 1.5)
            self.send_keys_slow(email_input, new_email)
            self.sleep(0.5, 1.5)
            chk_btn = self.driver.find_element_by_id(btn)
            chk_btn.click()
            self.sleep(6.5, 9.5)
            self.check_email_valid()

        return self  # daisy chain

    def select_opt(self, el, opt_text):
        sel = Select(el)
        sel.select_by_visible_text(opt_text)
        return self  # daisy chain

    def send_keys_slow(self, el, string):
        """
        send keys with random interval 0.2 - 0.9 sec
        """
        for char in string:
            el.send_keys(char)
            time.sleep(random.uniform(0.2, 0.9))
        return self  # daisy chain

    @staticmethod
    def sleep(sec_min, sec_max):
        time.sleep(random.uniform(sec_min, sec_max))

    def scroll_into_view(self, el):
        self.driver.execute_script(
            'arguments[0].scrollIntoView({behavior: "smooth"});', el)
        return self  # daisy chain


class SshTunnel(object):
    """
    spawn ssh tunnels for every proxy in list
    remote proxy should be listening on its local port
    ssh should authorize by private key
    :param config ConfigParser class
    """

    def __init__(self, config):
        self.kill_all_ssh()

        self.ssh_port = config.ssh_port
        self.ssh_usr = config.ssh_usr
        self.ssh_exe = config.ssh_exe
        self.proxy_file = config.proxy_file
        self.proxy_list = []
        self.pid = ''
        self.tunnel_list = []
        self.localhost = '127.0.0.1'
        self.localport = 8081
        self.parse_proxy()

    def kill_pid(self):
        """
        kill ssh tunnel from .spawn_tunnel() by pid
        """
        os.system('taskkill /F /PID %s' % self.pid)
        self.pid = ''

    @staticmethod
    def kill_all_ssh():
        """
        kill all running ssh processes
        """
        os.system('taskkill /F /IM ssh.exe')

    def parse_proxy(self):
        """
        parse proxy file and append proxies to list
        """
        with open(self.proxy_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    self.proxy_list.append(line)

    def spawn_tunnel(self, proxy):
        """
        for every proxy in the list
        spawn tunnel on localhost:8081 and upper ports
        """

        proxy_host, proxy_port = proxy.split(':')

        # cmd to spawn ssh tunnel, not optimized
        # ssh.exe -N -L localport:localhost:proxyport user@proxy -p sshport

        cmd = '%s -N -L %s:%s:%s %s@%s -p %s' % (
            self.ssh_exe, self.localport, self.localhost, proxy_port,
            self.ssh_usr, proxy_host, self.ssh_port)

        proc = subprocess.Popen(cmd)
        tunnel = '%s:%s' % (self.localhost, self.localport)
        print 'spawned ssh tunnel on %s to %s with PID:%s' % (tunnel, proxy,
                                                              proc.pid)

        self.pid = proc.pid
        return tunnel


if __name__ == '__main__':
    c = ConfigParser('gmx_robot.cfg')
    s = SshTunnel(c)
    for p in s.proxy_list:
        s.kill_all_ssh()
        tunn = s.spawn_tunnel(p)
        gmx = GmxRobot(config=c, proxy=tunn)
        gmx.run()
        print gmx.data
