# Copyright (C) 2013 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Request Handler for /notify endpoint."""

__author__ = 'alainv@google.com (Alain Vongsouvanh)'


import io
import json
import logging
import webapp2
import urllib2

from apiclient.http import MediaIoBaseUpload
from oauth2client.appengine import StorageByKeyName

from model import Credentials
import util


class NotifyHandler(webapp2.RequestHandler):
  """Request Handler for notification pings."""

  def post(self):
    """Handles notification pings."""
    logging.info('Got a notification with payload %s', self.request.body)
    data = json.loads(self.request.body)
    userid = data['userToken']
    # TODO: Check that the userToken is a valid userToken.
    self.mirror_service = util.create_service(
        'mirror', 'v1',
        StorageByKeyName(Credentials, userid, 'credentials').get())
    if data.get('collection') == 'locations':
      self._handle_locations_notification(data)
    elif data.get('collection') == 'timeline':
      self._handle_timeline_notification(data)

  def _handle_locations_notification(self, data):
    """Handle locations notification."""
    location = self.mirror_service.locations().get(id=data['itemId']).execute()
    lat = location.get('latitude')
    lng = location.get('longitude')
    logging.info('New location is %s, %s', lat, lng)

    url = "http://www.eventbrite.com/directory/json/?lat=%s&lng=%s&radius=0.5&q=EB_DEMO+2013" % (lat, lng)
    jsonObj = json.load(urllib2.urlopen(url))
    event_list = []
    cnt = 0;
    for eventObj in jsonObj["events"]:
        event_list.append('<li>' + eventObj["title"] + '</li>')
        cnt = cnt + 1
        if cnt > 4:
            break
    html = '<article><section><div class=\"text-normal\"><p style=\"color: #f16924;\">Nearby Events</p><ul class=\"text-x-small\">' + (''.join(event_list)) + '</section></article>'

    body = {
        'html': html,
        'location': location,
        'menuItems': [{'action': 'CUSTOM', 'id': 'social-stream', 'values': [{'displayName': 'Social Stream', 'iconUrl': 'https://fbcdn-profile-a.akamaihd.net/hprofile-ak-ash4/373119_15818120260_657956353_q.jpg'}]}, {'action': 'DELETE'}],
        'notification': {'level': 'DEFAULT'}
    }
    self.mirror_service.timeline().insert(body=body).execute()

  def _handle_timeline_notification(self, data):
    """Handle timeline notification."""
    for user_action in data.get('userActions', []):
      if user_action.get('type') == 'SHARE':
        # Fetch the timeline item.
        item = self.mirror_service.timeline().get(id=data['itemId']).execute()
        attachments = item.get('attachments', [])
        media = None
        if attachments:
          # Get the first attachment on that timeline item and do stuff with it.
          attachment = self.mirror_service.timeline().attachments().get(
              itemId=data['itemId'],
              attachmentId=attachments[0]['id']).execute()
          resp, content = self.mirror_service._http.request(
              attachment['contentUrl'])
          if resp.status == 200:
            media = MediaIoBaseUpload(
                io.BytesIO(content), attachment['contentType'],
                resumable=True)
          else:
            logging.info('Unable to retrieve attachment: %s', resp.status)
        body = {
            'text': 'Echoing your shared item: %s' % item.get('text', ''),
            'notification': {'level': 'DEFAULT'}
        }
        self.mirror_service.timeline().insert(
            body=body, media_body=media).execute()
        # Only handle the first successful action.
        break
      elif user_action.get('type') == 'CUSTOM' and user_action.get('payload') == 'social-stream':
        self._insert_social_stream()
      else:
        logging.info(
            "I don't know what to do with this notification: %s", user_action)

  def _insert_social_stream(self):
    json_data = json.load(urllib2.urlopen("http://www.eventbrite.com/ajax/event/7778380345/experience/more/?next=0"))

    messages = []

    for count in range(0,5):

      data = json_data.get('data')[count]

      logging.info (data.get('text'))

      message = {'html': 'on', 'text': self._html(data), 'imageUrl': None}

      self._generic_insert_item([message])

  def _html(self,data):

      text = data.get('text')
      image = data.get('images').get('low_resolution') if data.get('images') else ""

      logging.info ("Image URL :"+image)

      base_html = '<article class="photo" style="background-color:#00a2a5">'
      if image:
        base_html = base_html + '<img src="' + image + '" height="100%">'
      base_html = base_html + '<div class="photo-overlay"/><section>'
      if text:
        base_html = base_html + '<p class="text-auto-size">' + text + '</p>'
      base_html = base_html + '</section></article>'
      logging.info("HTML: " + base_html)

      return base_html


  def _generic_insert_item(self, messages):
      """
      Post a bundle of timelines.

      Messages is a collection of Message object
      message = {
          html:'on',
          text:'text',
          imageUrl:'imageUrl',
          isBundleCover:'isBundleCover',
          bundleId:'bundleId',}
      """
      logging.info ('Inserting timeline item for messages total : %s '% len(messages))

      #Interate over a list of messages and send them
      for message in messages:
          body = {
              'notification': {'level': 'DEFAULT'}
          }
          if message['html'] == 'on':
              body['html'] = message['text']
          else:
              body['text'] = message['text']

          media_link = message['imageUrl']

          if media_link:
              if media_link.startswith('/'):
                  media_link = util.get_full_url(self, media_link)
              resp = urlfetch.fetch(media_link, deadline=20)
              media = MediaIoBaseUpload(
              io.BytesIO(resp.content), mimetype='image/jpeg', resumable=True)
          else:
            media = None

          self.mirror_service.timeline().insert(body=body, media_body=media).execute()

NOTIFY_ROUTES = [
    ('/notify', NotifyHandler)
]
