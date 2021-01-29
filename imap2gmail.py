# imap2gmail
# version 20210129-1
#
# Move messages via IMAP from 
# imaps://sourceAccount:sourcePassword@sourceServer:sourcePort/sourceMailbox
# to 
# imaps://destAccount:destPassword@destServer:destPort/destMailbox
# The parameters for these IMAP-TLS URLs can be set just below.
# TODO: 
# - handle messages that are too large or otherwise unable to be 
#   appended to the destination mailbox
# - read configuration from command-line parameters
# - read configuration (including passwords) from separate config file
#
# See also NOTES

import imaplib, email

sourceAccount = '[the source account username is not set]'
sourcePassword = ''
sourceServer = '[the source account server address is not set]'
sourcePort = 993
sourceMailbox = 'INBOX'
destAccount = '[the destination account username is not set]'
destPassword = ''
destServer = '[the destination account server address is not set]'
destPort = 993
destMailbox = 'INBOX'
destMaxSize = 25000000

source = imaplib.IMAP4_SSL(sourceServer, sourcePort)
source.login( sourceAccount, sourcePassword )
result, [ numMessages ] = source.select( sourceMailbox )
if numMessages != b'0' :
    dest = imaplib.IMAP4_SSL(destServer, destPort)
    dest.login( destAccount, destPassword )
    result, discard = dest.select( destMailbox )

    newMessages = list()
    result, [ nums ] = source.uid('search',None,'ALL')
    msgUids = nums.split()
    
    for msgUid in msgUids:
        # Two calls may be expensive, but since we have to futz with msgDate
        # it minimizes memory use in the case that data is very large
        result, data = source.uid('fetch', msgUid, 'RFC822')
        result, [ msgDate ] = source.uid('fetch', msgUid, 'INTERNALDATE')

        newData = data[0][1] # the actual message data

        # to keep imaplib from trying to interpret msgDate when appending
        # to the new mailbox, it must be in double quotes
        msgDate = '"' + msgDate.split(b'"')[1].decode() + '"'
        if len(newData) > destMaxSize:
            newMsg = email.message_from_bytes( newData )
            # if message size too large, check if there are attachments
            if newMsg.is_multipart():
                # if there are attachments, check their sizes
                # see if some combination of removal of attachments results in a message
                #  that's not too big 
                # then rewrite message, post attachments elsewhere, etc (probably via
                #  a separate function so I can then also use it if adding to dest
                #  fails)
                True
        result, data = dest.append(destMailbox,None,msgDate,newData)
        if result == b'OK':
            source.uid('store', msgUid, '+FLAGS', '\\Deleted')
    result, discard = source.expunge()