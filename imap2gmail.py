# imap2gmail
#
# Move messages via IMAP from
# imaps://sourceAccount:sourcePassword@sourceServer:sourcePort/sourceMailbox
# to
# imaps://destAccount:destPassword@destServer:destPort/destMailbox
# The parameters for these IMAP-TLS URLs can be set just below in the
# USER ACCOUNT CONFIGURATION section
# TODO:
# - handle messages that are too large or otherwise unable to be
#   appended to the destination mailbox
# - read configuration from command-line parameters
#
# See also NOTES

import sys
import os
import email.message
import email.policy
import imaplib
import email
import configparser
from config_path import ConfigPath
import stat


def default_config():
    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        'sourceAccount': 'IMAP',
        'destAccount': 'Gmail',
        'inbox': 'INBOX',
        'sent': 'Sent',
        'archive': 'Archive',
        'attachmentRewrite': 'no',
        'attachmentDir': '',
        'errorBehavior': 'move',
        'errorMailbox': '',
        'port': '993'
    }
    config['Gmail'] = {
        'server': 'imap.gmail.com',
        'user': '',
        'password': '',
        'maxSize': '25000000',
        'archive': '"[Gmail]/All Mail"',
                'sent': '"[Gmail]/Sent Mail"'
    }
    config['Office'] = {
        'server': 'outlook.office365.com',
        'user': '',
        'password': '',
                'sent': '"Sent Items"'
    }
    config['IMAP'] = {}
    return config


vendor = 'aleph0.com'
appname = 'imap2gmail'
confPath = ConfigPath(appname, vendor, filetype='.ini')
confFile = confPath.readFilePath()

if confFile is None:
    config = default_config()
    newConfPath = confPath.saveFilePath(mkdir=True)
    with open(newConfPath, 'w',) as newConfigFile:
        config.write(newConfigFile)
    os.chmod(newConfPath, stat.S_IRUSR | stat.S_IWUSR)
    raise FileNotFoundError('No configuration file found; new file ' +
                            os.fspath(newConfPath) + ' created. Edit to configure.')

config = configparser.ConfigParser()
config.read(confFile)
if not 'sourceAccount' in config['DEFAULT']:
    raise KeyError('No source account set in config file ' +
                   os.fspath(confPath))
if not 'destAccount' in config['DEFAULT']:
    raise KeyError('No destination account set in config file ' +
                   os.fspath(confPath))
sourceAccount = config['DEFAULT']['sourceAccount']
destAccount = config['DEFAULT']['destAccount']
if not sourceAccount in config or not 'server' in config[sourceAccount] or not 'user' in config[sourceAccount] or not 'password' in config[sourceAccount]:
    raise KeyError('Source account ' + sourceAccount +
                   ' settings are incomplete. Edit ' + os.fspath(confPath))
if not destAccount in config or not 'server' in config[destAccount] or not 'user' in config[destAccount] or not 'password' in config[destAccount]:
    raise KeyError('Destination account ' + destAccount +
                   ' settings are incomplete. Edit ' + os.fspath(confPath))

dest = config[destAccount]
source = config[sourceAccount]
sourceServer = source['server']
sourcePort = source.getint('port')
sourceAccount = source['user']
sourcePassword = source['password']
sourceInbox = source['inbox']
sourceSent = source['sent']
sourceArchive = source['archive']
sourceErrorMailbox = source['errorMailbox']
destServer = dest['server']
destPort = dest.getint('port')
destAccount = dest['user']
destPassword = dest['password']
destMaxSize = dest.getint('maxSize')
destInbox = dest['inbox']
destArchive = dest['archive']
destSent = dest['sent']

attachmentRewrite = config['DEFAULT'].getboolean('attachmentRewrite')
attachmentDir = config['DEFAULT']['attachmentDir']
errorBehavior = config['DEFAULT']['errorBehavior']

msgPolicy = email.policy.SMTP.clone(refold_source='none')
mailboxes = {
    (sourceInbox, destInbox),
    (sourceArchive, destArchive),
    (sourceSent, destSent)
}
destConnected = False
source = imaplib.IMAP4_SSL(sourceServer, sourcePort)
result = source.login(sourceAccount, sourcePassword)
for (sourceMailbox, destMailbox) in mailboxes:
    result = source.select(sourceMailbox)
    result = source.expunge()
    result, [numMessages] = source.select(sourceMailbox)
    if numMessages != b'0':
        if not destConnected:
            dest = imaplib.IMAP4_SSL(destServer, destPort)
            dest.login(destAccount, destPassword)
            destConnected = True
        result = dest.select(destMailbox)
        result, [nums] = source.uid('search', None, 'ALL')
        msgUids = nums.split()
        for msgUid in msgUids:
            # Instead of checking all this first, should we just attempt to put it
            # on the destination and handle problems if not appendable?
            # Two calls may be expensive, but since we have to futz with msgDate
            # it minimizes memory use in the case that data is very large
            result, data = source.uid('fetch', msgUid, 'RFC822')
            result, [msgDate] = source.uid('fetch', msgUid, 'INTERNALDATE')

            # to keep imaplib from trying to interpret msgDate when appending
            # to the new mailbox, it must be in double quotes
            msgDate = '"' + msgDate.split(b'"')[1].decode() + '"'

            newData = data[0][1]  # the actual message data
            if (len(newData) > destMaxSize) & bool(attachmentRewrite):
                newMsg = email.message_from_bytes(
                    newData, None, policy=msgPolicy)
                if newMsg.is_multipart():
                    # some sort of id, could be based on boundary or some content-id
                    msgBoundary = newMsg.get_boundary()
                    for msgPart in newMsg.walk():
                        if msgPart.get_content_disposition() != None:
                            # get size could include using the size param of
                            # the content-disposition or something else
                            msgHeaders = msgPart.items()
                            # probably need to make these things 'safe'
                            attName = msgPart.get_filename('attachment')
                            attDate = msgPart['Content-Disposition'].params['modification-date']
                            if attDate == None:
                                attDate = msgPart['Content-Dispositon'].params['creation-date']
                            attPath = os.path.join(attachmentDir, attName)
                            with open(attPath, 'wb') as attFile:
                                attFile.write(msgPart.get_content())
                            # modify attachment to have appropriate date
                            msgString = 'This email has been modfied from the original, which '
                            msgString += 'was too large to deliver. The following attachment '
                            msgString += "was removed:\n\n"
                            msgString += "Original headers:\n"
                            for headerName, headerValue in msgHeaders:
                                msgString += headerName + ' : ' + headerValue + "\n"
                            msgString += "\nAttachent saved as:\n"
                            msgString += attPath + "\n"
                            msgPart.set_content(
                                msgString, disposition='inline')
                msgFrom = bool(newMsg.get_unixfrom())
                newData = newMsg.as_bytes(msgFrom)
                if len(newData) > destMaxSize:
                    True
            try:
                # for Google's standard 'BAD' (TOOBIG) response for a message
                # that's too large, an exception is thrown rather than returning
                # the result
                result, data = dest.append(destMailbox, None, msgDate, newData)
                if result == 'OK':
                    source.uid('store', msgUid, '+FLAGS', '\\Deleted')
                else:
                    raise imaplib.IMAP4.error
            except imaplib.IMAP4.error as exception:
                # Unfortunately this doesn't work since an exception is raised
                # and it's not reliable to parse the result, but maybe for gmail
                # specifically we can use the 'TOOBIG' tag? The exception seems
                # to have only the string with no other data
                print('Error moving message with uid ' + msgUid.decode() +
                      '(message date ' + msgDate + ')', file=sys.stderr)
                print(' from ' + sourceAccount + '@' + sourceServer +
                      '/' + sourceMailbox, file=sys.stderr)
                print(' to ' + destAccount + '@' + destServer +
                      '/' + destMailbox, file=sys.stderr)
                print(' (' + str(exception) + ')', file=sys.stderr)

                if (sourceMailbox != sourceErrorMailbox) & (errorBehavior == 'move'):
                    result = source.uid('copy', msgUid, sourceErrorMailbox)
                    if result[0] == b'OK':
                        print(' Moved it to ' + sourceAccount + '@' + sourceServer +
                              '/' + sourceErrorMailbox + ' instead.', file=sys.stderr)
                        source.uid('store', msgUid, '+FLAGS', '\\Deleted')
                    else:
                        print(' Left it in place instead.', file=sys.stderr)
                else:
                    print(' Left it in place instead.', file=sys.stderr)
if destConnected:
    dest.close()
    dest.logout()
source.close()
source.logout()
