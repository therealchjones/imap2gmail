# imap2gmail
# version 20210201-1
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
# - read configuration (including passwords) from separate config file
#
# See also NOTES

# USER ACCOUNT CONFIGURATION ------------------------------------------
sourceAccount = '[the source account username is not set]'
sourcePassword = '[the source account password is not set]'
sourceServer = '[the source account server is not set]'
sourcePort = 993
sourceMailbox = 'INBOX'
sourceErrorMailbox = '[the source error mailbox is not set]'
destAccount = '[the destination account username is not set]'
destPassword = ''
destServer = '[the destination account server address is not set]'
destPort = 993
destMailbox = 'INBOX'
destMaxSize = 25000000 # bytes
attachmentRewrite = False # True, False, or None
attachmentDir = '[the local attachment directory is not set]'
errorBehavior = 'move' # 'move' to sourceErrorMailbox, 
                       # 'save' in sourceMailbox (will be seen next time)
# end of USER ACCOUNT CONFIGURATION -----------------------------------

# nothing below here is end-user configurable -------------------------
import imaplib, os, sys
import email
import email.policy, email.message

source = imaplib.IMAP4_SSL(sourceServer, sourcePort)
result = source.login( sourceAccount, sourcePassword )
result, [ numMessages ] = source.select( sourceMailbox )
if numMessages != b'0' :
    msgPolicy = email.policy.SMTP.clone(refold_source='none')

    dest = imaplib.IMAP4_SSL(destServer, destPort)
    dest.login( destAccount, destPassword )
    result = dest.select( destMailbox )

    result, [ nums ] = source.uid('search',None,'ALL')
    msgUids = nums.split()
    
    for msgUid in msgUids:
        # Instead of checking all this first, should we just attempt to put it
        # on the destination and handle problems if not appendable?
        # Two calls may be expensive, but since we have to futz with msgDate
        # it minimizes memory use in the case that data is very large
        result, data = source.uid('fetch', msgUid, 'RFC822')
        result, [ msgDate ] = source.uid('fetch', msgUid, 'INTERNALDATE')

        # to keep imaplib from trying to interpret msgDate when appending
        # to the new mailbox, it must be in double quotes
        msgDate = '"' + msgDate.split(b'"')[1].decode() + '"'

        newData = data[0][1] # the actual message data
        if ( len(newData) > destMaxSize ) & bool(attachmentRewrite):
            newMsg = email.message_from_bytes( newData, None, policy=msgPolicy )
            if newMsg.is_multipart():
                # some sort of id, could be based on boundary or some content-id
                msgBoundary = newMsg.get_boundary()
                for msgPart in newMsg.walk() :
                    if msgPart.get_content_disposition() != None :
                        # get size could include using the size param of 
                        # the content-disposition or something else
                        msgHeaders = msgPart.items()
                        attName = msgPart.get_filename('attachment') # probably need to make these things 'safe'
                        attDate = msgPart['Content-Disposition'].params['modification-date']
                        if attDate == None:
                            attDate = msgPart['Content-Dispositon'].params['creation-date']
                        attPath = os.path.join(attachmentDir, attName)
                        with open(attPath,'wb') as attFile:
                            attFile.write( msgPart.get_content() )
                        # modify attachment to have appropriate date
                        msgString = 'This email has been modfied from the original, which '
                        msgString += 'was too large to deliver. The following attachment '
                        msgString += "was removed:\n\n"
                        msgString += "Original headers:\n"
                        for headerName, headerValue in msgHeaders:
                            msgString += headerName + ' : ' + headerValue + "\n"
                        msgString += "\nAttachent saved as:\n"
                        msgString += attPath + "\n"
                        msgPart.set_content(msgString, disposition='inline')
            msgFrom = bool( newMsg.get_unixfrom() )
            newData = newMsg.as_bytes(msgFrom)
            if len(newData) > destMaxSize:
                True
        try:
            # for Google's standard 'BAD' (TOOBIG) response for a message
            # that's too large, an exception is thrown rather than returning
            # the result
            result, data = dest.append(destMailbox,None,msgDate,newData)
            if result == 'OK': 
                source.uid('store', msgUid, '+FLAGS', '\\Deleted')
            else:
                raise imaplib.IMAP4.error
        except imaplib.IMAP4.error as exception:
            # Unfortunately this doesn't work since an exception is raised
            # and it's not reliable to parse the result, but maybe for gmail
            # specifically we can use the 'TOOBIG' tag? The exception seems
            # to have only the string with no other data
            print('Error moving message with uid ' + msgUid.decode() + '(message date ' + msgDate + ')' ,file=sys.stderr)
            print(' from ' + sourceAccount + '@' + sourceServer + '/' + sourceMailbox,file=sys.stderr)
            print(' to ' + destAccount + '@' + destServer + '/' + destMailbox,file=sys.stderr)
            print(' (' + str(exception) + ')' )

            if ( sourceMailbox != sourceErrorMailbox ) & ( errorBehavior == 'move' ):
                result = source.uid('copy', msgUid, sourceErrorMailbox)
                if result[0] == b'OK':
                    print(' Moved it to ' + sourceAccount + '@' + sourceServer + '/' + sourceErrorMailbox + ' instead.', file=sys.stderr)
                    source.uid('store', msgUid, '+FLAGS', '\\Deleted')
                else:
                    print(' Left it in place instead.', file=sys.stderr)
            else:
                print(' Left it in place instead.', file=sys.stderr)
    dest.close()
    dest.logout()
source.close()
source.logout()