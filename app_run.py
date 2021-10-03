import logging
import json
import os
import re
from datetime import datetime
from datetime import timedelta

logging.basicConfig(level=logging.WARNING)

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
AIRTABLE_API_KEY = os.environ['AIRTABLE_API_KEY']
AIRTABLE_BASE = os.environ['AIRTABLE_BASE']
AIRTABLE_NAME = os.environ['AIRTABLE_NAME']
PROXY_URL = os.environ['PROXY_URL']
START_TIME = os.environ['START_TIME']
END_TIME = os.environ['END_TIME']
MINUS_DAY = os.environ['MINUS_DAY']

from slack_bolt.app import App
from slack_sdk.errors import SlackApiError
from slack_bolt.adapter.flask import SlackRequestHandler

app = App(
    token = SLACK_BOT_TOKEN,
    signing_secret = SLACK_SIGNING_SECRET
)

import airtable

at = airtable.Airtable(AIRTABLE_BASE, AIRTABLE_API_KEY)

def insertRecord(record, userId, blockInfo, logger):
    try:
        dateList = queryUploadedDate(logger, userId)
        if isNotRepeat(logger, record["Date"], dateList) and isNotOver(logger, record["Date"]):
            logger.debug(record)
            res = at.create(AIRTABLE_NAME, record)
            recordInfo = {
                "id":res["id"],
                "date": record["Date"]
            }
            recordInfoString = json.dumps(recordInfo)

            # Handle Optional Column
            if record["Comment"] is None:
                comment = ""
            else:
                comment = record["Comment"]

            app.client.chat_postMessage(
                token =  SLACK_BOT_TOKEN,
                channel =  userId,
                text = "上傳成功囉，本次上傳紀錄如下",
                attachments = [{
                    "color": "#f2c744",
                    "blocks": [{
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*運動時間：* " +
                                record["Duration"] +
                                "\n\n*運動日期：* " +
                                record["Date"] +
                                "\n\n*運動項目：* " +
                                record["Type"] +
                                "\n\n*備註：* " +
                                comment
                        },
                        "accessory": {
                            "type": "image",
                            "image_url": record["Attachments"][0]["url"],
                            "alt_text": "Thumbnail"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [{
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "刪除這筆紀錄",
                                "emoji": True
                            },
                            "style": "danger",
                            "value": recordInfoString,
                            "action_id": "delete_action",
                            "confirm": {
                                "title": {
                                    "type": "plain_text",
                                    "text": "真的要刪除嗎"
                                },
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "刪除 " + record["Date"] +"日 的運動紀錄"
                                },
                                "confirm": {
                                    "type": "plain_text",
                                    "text": "Delete"
                                },
                                "deny": {
                                    "type": "plain_text",
                                    "text": "Cancel"
                                }
                            },
                        }]
                    }]
                }]
            )
        else:
            blockInfoString = json.dumps(blockInfo)
            app.client.chat_postMessage(
                token =  SLACK_BOT_TOKEN,
                channel = userId,
                text =  "運動日期有誤，請再次填寫詳細資料",
                attachments = [{
                    "color": "#f2c744",
                    "blocks": [{
                        "type": "actions",
                        "elements": [{
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "填寫詳細資料",
                                "emoji": True
                            },
                            "style": "primary",
                            "value": blockInfoString,
                            "action_id": "open_modal_action"
                        }]
                    }]
                }]
            )
    except Exception as e:
        logger.error(e)
        blockInfoString = json.dumps(blockInfo)
        app.client.chat_postMessage(
            token =  SLACK_BOT_TOKEN,
            channel = userId,
            text =  "上傳失敗，請再次填寫詳細資料",
            attachments = [{
                "color": "#f2c744",
                "blocks": [{
                    "type": "actions",
                    "elements": [{
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "填寫詳細資料",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": blockInfoString,
                        "action_id": "open_modal_action"
                    }]
                }]
            }]
        )

def isNotRepeat(logger, sport_date, dateList):
    try:
        if sport_date not in dateList:
            logger.debug("isNotRepeat!")
            return True
        else:
            logger.debug("isRepeat!")
            return False
    except Exception as e:
        logger.error(e)

def isNotOver(logger, sport_date):
    logger.debug(sport_date)
    try:
        startDate = datetime.strptime(START_TIME, "%Y-%m-%d")
        endDate = datetime.strptime(END_TIME, "%Y-%m-%d")
        sportDateValue = datetime.strptime(sport_date, "%Y-%m-%d")
        today = (datetime.utcnow() + timedelta(hours=8)).date()
        today_n = (datetime.utcnow() - timedelta(days=int(MINUS_DAY))).date()
        logger.debug("today is " + str(today))
        logger.debug("today - n is " + str(today_n))
        if (sportDateValue >= startDate and sportDateValue <= endDate) and (sportDateValue.date() >= today_n and sportDateValue.date() <= today):
            logger.debug("isNotOver!")
            return True
        else:
            logger.debug("isOver!")
            return False
    except Exception as e:
        logger.error(e)

def queryUploadedDate(logger, user_id):
    try:
        filterByFormula = "{ID} = '" + user_id + "'"
        logger.debug(filterByFormula)
        res = at.get(table_name = "Table 1", fields = ['ID', 'Date'], filter_by_formula=filterByFormula)
        logger.debug(res)
        dateSet = set()
        for record in res["records"]:
            if "Date" in record["fields"]:
                dateSet.add(record["fields"]["Date"])
        return sorted(dateSet)
    except Exception as e:
        logger.error(e)

@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()

@app.event("file_shared")
def handle_file(event, client, logger):
    logger.debug("看這裡")
    logger.debug(event)
    try:
        if event["channel_id"][0] == "D":
            res = client.files_info (
                token = SLACK_BOT_TOKEN,
                file = event["file_id"]
            )

            logger.debug(res)
            if res["file"]["mimetype"].split("/")[0] == "image":


                if res["file"]["original_w"] >= 720:
                    thumb_720_public = res["file"]["thumb_720"].replace("files.slack.com", PROXY_URL)
                elif res["file"]["original_w"] >= 480:
                    thumb_720_public = res["file"]["thumb_480"].replace("files.slack.com", PROXY_URL)
                elif res["file"]["original_w"] >= 360:
                    thumb_720_public = res["file"]["thumb_360"].replace("files.slack.com", PROXY_URL)
                else:
                    thumb_720_public = res["file"]["url_private"].replace("files.slack.com", PROXY_URL)

                # thumb_720_public = res["file"]["thumb_720"].replace("files.slack.com", PROXY_URL)
                fileName = res["file"]["name"]
                fileLink = res["file"]["url_private"].replace("files.slack.com", PROXY_URL)

                fileInfo = {
                    "thumb_720_public": thumb_720_public,
                    "fileLink": fileLink,
                    "fileName": fileName
                }

                blockInfo = {
                    "type": "section",
                    "block_id": "sport_image",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*檔案名稱*\n" + fileInfo["fileName"]
                    },
                    "accessory": {
                        "type": "image",
                        "image_url": fileInfo["thumb_720_public"],
                        "alt_text": fileInfo["fileLink"]
                    }
                }


                blockInfoString = json.dumps(blockInfo)

                logger.debug(fileInfo)

                client.chat_postMessage(
                    channel = event["user_id"],
                    user = event["user_id"],
                    text =
                        "感謝參與EWC居家健康月！上傳作業尚未完成，請點選「填寫詳細資料」完成下一步步驟",
                    attachments = [{
                        "color": "#f2c744",
                        "blocks": [{
                            "type": "actions",
                            "elements": [{
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "填寫詳細資料",
                                    "emoji": True
                                },
                                "style": "primary",
                                "value": blockInfoString,
                                "action_id": "open_modal_action"
                            }]
                        }]
                    }]
                )
            else:
                if event["file_id"] != "F028880B3QQ" and event["file_id"] != "F027X9F0F2M" and event["file_id"] != "F02BDP60S6L":
                    client.chat_postMessage(
                        channel = event["user_id"],
                        user = event["user_id"],
                        text =
                            "感謝參與EWC居家健康月！但是上傳的似乎不是一張圖片，請重新上傳正確副檔名的圖片！"
                    )
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.action("open_modal_action")
def handle_file_modal(client, body, ack, logger):
    ack()
    logger.debug(body)
    try:
        client.chat_update(
            token = SLACK_BOT_TOKEN,
            channel = body["container"]["channel_id"],
            ts = body["container"]["message_ts"],
            text = body["message"]["text"],
            attachments =  [{
                "blocks": [{
                    "type": "context",
                    "elements": [{
                        "type": "plain_text",
                        "text": "編輯視窗已開啟",
                        "emoji": True
                    }]
                }]
            }]
        )

        valueObj = json.loads(body["actions"][0]["value"])
        # 顯示第一階段
        client.views_open(
            trigger_id = body["trigger_id"],
            view = {
                "type": "modal",
                "callback_id": "modal_view",
                "notify_on_close": True,
                "title": {
                    "type": "plain_text",
                    "text": "填寫運動紀錄",
                    "emoji": True
                },
                # "submit": {
                #     "type": "plain_text",
                #     "text": "Submit",
                #     "emoji": True
                # },
                # "close": {
                #     "type": "plain_text",
                #     "text": "Cancel",
                #     "emoji": True
                # },
                "blocks": [
                valueObj,
                {
                    "type": "section",
                    "block_id": "sport_duration",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*運動時間*"
                    },
                    "accessory": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "選擇運動時間",
                            "emoji": True
                        },
                        "options": [{
                            "text": {
                                "type": "plain_text",
                                "text": "30分鐘",
                                "emoji": True
                            },
                            "value": "30分鐘"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "30~40分鐘",
                                "emoji": True
                            },
                            "value": "30~40分鐘"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "40~50分鐘",
                                "emoji": True
                            },
                            "value": "40~50分鐘"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "50~60分鐘",
                                "emoji": True
                            },
                            "value": "50~60分鐘"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "超過1小時",
                                "emoji": True
                            },
                            "value": "超過1小時"
                        }],
                        "action_id": "sport_duration_action"
                    }
                },
                # {
                #     "type": "section",
                #     "block_id": "sport_date",
                #     "text": {
                #         "type": "mrkdwn",
                #         "text": "*運動日期*"
                #     },
                #     "accessory": {
                #         "type": "datepicker",
                #         "initial_date": "2021-07-01",
                #         "placeholder": {
                #             "type": "plain_text",
                #             "text": "Select a date",
                #             "emoji": True
                #         },
                #         "action_id": "sport_date_action"
                #     }
                # },
                # {
                #     "type": "input",
                #     "block_id": "sport_type",
                #     "element": {
                #         "type": "plain_text_input",
                #         "action_id": "sport_type_action"
                #     },
                #     "label": {
                #         "type": "plain_text",
                #         "text": "運動項目",
                #         "emoji": True
                #     }
                # },
                # {
                #     "type": "input",
                #     "block_id": "comment",
                #     "element": {
                #         "type": "plain_text_input",
                #         "action_id": "comment_action"
                #     },
                #     "optional": True,
                #     "label": {
                #         "type": "plain_text",
                #         "text": "備註",
                #         "emoji": True
                #     }
                # }
                ]
            }
        )
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.action("sport_duration_action")
def handle_some_action(client, ack, body, logger):
    ack()
    logger.debug(body)
    # 顯示第二階段
    try:
        if len(body["view"]["blocks"]) < 3:
            secondBlock = {
                "type": "section",
                "block_id": "sport_date",
                "text": {
                    "type": "mrkdwn",
                    "text": "*運動日期*"
                },
                "accessory": {
                    "type": "datepicker",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a date",
                        "emoji": True
                    },
                    "action_id": "sport_date_action",
                }
            }
            startTimeText=str(int(START_TIME.split('-')[1])) + '/' + str(int(START_TIME.split('-')[2]))
            endTimeText=str(int(END_TIME.split('-')[1])) + '/' + str(int(END_TIME.split('-')[2]))

            secondBlockAlert={
                "type": "context",
                "elements": [{
                    "type": "plain_text",
                    "text": "請填寫" + startTimeText +"～" + endTimeText + "之間的日期，不能重複上傳相同日期，並且只能上傳當日～前" + MINUS_DAY + "天的日期",
                    "emoji": True
                }]
            }
            newBlocks = body["view"]["blocks"]
            newBlocks.append(secondBlock)
            newBlocks.append(secondBlockAlert)

            client.views_update(
                view_id =  body["view"]["id"],
                hash =  body["view"]["hash"],
                view = {
                    "type": body["view"]["type"],
                    "callback_id": body["view"]["callback_id"],
                    "notify_on_close": True,
                    "title": body["view"]["title"],
                    "blocks": newBlocks,
                }
            )
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.action("sport_date_action")
def handle_some_action(client, ack, body, logger):
    ack()
    logger.debug(body)
    try:
        sport_date = body["actions"][0]["selected_date"]
        user_id = body["user"]["id"]
        dateList = queryUploadedDate(logger, user_id)
        logger.debug(dateList)
        isNotOverResult=isNotOver(logger, sport_date)
        isNotRepeatResult=isNotRepeat(logger, sport_date, dateList)

        errorInfo=""

        if isNotRepeatResult==False:
            errorInfo="運動日期有誤（不能上傳重複日期）"

        if isNotOverResult==False:
            # errorInfo="不能上傳當日及前" + MINUS_DAY + "天以外的日期/上傳日期超出活動期間"
            errorInfo="運動日期有誤（僅能上傳當日～" + MINUS_DAY + "日前之資料，並且需指定活動期間內之日期）"
        logger.debug(errorInfo)

        # 判斷首次進入
        if len(body["view"]["blocks"]) < 5:
            if isNotOverResult and isNotRepeatResult:
                logger.debug("首次進入，並且符合條件，顯示第三階段")
                logger.debug(body["view"]["blocks"][3]["elements"][0]["text"])
                body["view"]["blocks"][3]["elements"][0]["text"] = ":check-carbon: 運動日期正確"

                thirdBlock = {
                    "type": "input",
                    "block_id": "sport_type",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "sport_type_action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "運動項目",
                        "emoji": True
                    }
                }
                forthBlock = {
                    "type": "input",
                    "block_id": "comment",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "comment_action"
                    },
                    "optional": True,
                    "label": {
                        "type": "plain_text",
                        "text": "備註",
                        "emoji": True
                    }
                }
                newBlocks = body["view"]["blocks"]
                newBlocks.append(thirdBlock)
                newBlocks.append(forthBlock)

                client.views_update(
                    view_id = body["view"]["id"],
                    hash = body["view"]["hash"],
                    view = {
                        "type": body["view"]["type"],
                        "callback_id": body["view"]["callback_id"],
                        "notify_on_close": True,
                        "title": body["view"]["title"],
                        "blocks": newBlocks,
                        "submit": {
                            "type": "plain_text",
                            "text": "Submit",
                            "emoji": True
                        },
                        "close": {
                            "type": "plain_text",
                            "text": "Cancel",
                            "emoji": True
                        },
                        # submit_disabled: true,
                    }
                )
            else:
                logger.debug("首次進入，但不符合條件，顯示錯誤訊息")
                # body["view"]["blocks"][3]["elements"][0]["text"] = ":error-carbon: 此日期已有上傳紀錄/日期超出比賽範圍\n目前已有上傳的日期有：" + '、'.join(dateList)
                body["view"]["blocks"][3]["elements"][0]["text"] = ":error-carbon: " + errorInfo
                logger.debug(body)

                client.views_update(
                    view_id = body["view"]["id"],
                    hash = body["view"]["hash"],
                    view = {
                        "type": "workflow_step",
                        "callback_id": body["view"]["callback_id"],
                        # "notify_on_close": True,
                        "blocks": body["view"]["blocks"],
                        "submit_disabled": True
                    }
                )
        else:
            if isNotOverResult and isNotRepeatResult:
                logger.debug("非首次進入，符合條件，顯示OK訊息")
                body["view"]["blocks"][3]["elements"][0]["text"] = ":check-carbon: 運動日期正確"
                client.views_update(
                    view_id = body["view"]["id"],
                    hash = body["view"]["hash"],
                    view = {
                        "type": "modal",
                        "callback_id": body["view"]["callback_id"],
                        "notify_on_close": True,
                        "title": {
                            "type": "plain_text",
                            "text": "填寫運動紀錄",
                            "emoji": True
                        },
                        "blocks": body["view"]["blocks"],
                        "submit": {
                            "type": "plain_text",
                            "text": "Submit",
                            "emoji": True
                        },
                        "close": {
                            "type": "plain_text",
                            "text": "Cancel",
                            "emoji": True
                        },
                    }
                )
            else:
                logger.debug("非首次進入，不符合條件，顯示NG訊息")
                # body["view"]["blocks"][3]["elements"][0]["text"] = ":error-carbon: 此日期已有上傳紀錄/日期超出比賽範圍\n目前已有上傳的日期有：" + '、'.join(dateList)
                body["view"]["blocks"][3]["elements"][0]["text"] = ":error-carbon: " + errorInfo
                client.views_update(
                    view_id = body["view"]["id"],
                    hash = body["view"]["hash"],
                    view = {
                        "type": "workflow_step",
                        "callback_id": body["view"]["callback_id"],
                        # "notify_on_close": True,
                        "blocks": body["view"]["blocks"],
                        "submit_disabled": True
                    }
                )
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

# Modal Cancel
@app.view({
    "callback_id": "modal_view",
    "type": "view_closed"
})
def handle_modal_cancel(client, body, ack, logger):
    ack()
    blockInfoString = json.dumps(body["view"]["blocks"][0])
    try:
        client.chat_postMessage(
            channel = body["user"]["id"],
            text =  "本次上傳已取消，如要上傳，請再次填寫詳細資料",
            attachments = [{
                "color": "#f2c744",
                "blocks": [{
                    "type": "actions",
                    "elements": [{
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "填寫詳細資料",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": blockInfoString,
                        "action_id": "open_modal_action"
                    }]
                }]
            }]
        )
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

# After Modal Submit
@app.view({
    "callback_id": "modal_view",
    "type": "view_submission"
})
def handle_file_modal_view(view, body, ack, logger):
    ack()
    logger.debug(body)
    try:
        sport_thumbnail = view["blocks"][0]["accessory"]["image_url"]
        sport_image_link = view["blocks"][0]["accessory"]["alt_text"]
        sport_date = view["state"]["values"]["sport_date"]["sport_date_action"]["selected_date"]
        sport_duration_option = view["state"]["values"]["sport_duration"]["sport_duration_action"]["selected_option"]
        sport_type = view["state"]["values"]["sport_type"]["sport_type_action"]["value"]
        if sport_duration_option is not None:
            sport_duration = sport_duration_option["value"]

        comment = view["state"]["values"]["comment"]["comment_action"]["value"]

        # res = client.users_info(
        #     token = SLACK_BOT_TOKEN,
        #     user = body["user"]["id"]
        # )
        # userEmail = res["user"]["profile"]["email"]

        # timestampStr = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d  %H:%M:%S")
        timestamp = (datetime.utcnow() + timedelta(hours=8))
        # timestampVal = datetime.timestamp(timestampStr)
        timestampVal = timestamp.isoformat();
        logger.debug(timestampVal)

        record = {
            #"Email": userEmail,
            "ID": body["user"]["id"],
            "Attachments": [{
                "url": sport_thumbnail
            }],
            "Duration": sport_duration,
            "Date": sport_date,
            "Type": sport_type,
            "Comment": comment,
            "URL": sport_image_link,
            "Timestamp" : timestampVal
        }
        insertRecord(record, body["user"]["id"], body["view"]["blocks"][0], logger)
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.action("delete_action")
def handle_delete_action(client, body, ack, logger):
    ack()
    logger.debug(body)
    try:
        valueObj = json.loads(body["actions"][0]["value"])
        at.delete(AIRTABLE_NAME, valueObj["id"])
        client.chat_postMessage(
            channel = body["user"]["id"],
            text =  "已成功刪除 "+ valueObj["date"] +" 日的運動記錄"
        )
        client.chat_update(
            token = SLACK_BOT_TOKEN,
            channel = body["container"]["channel_id"],
            ts = body["container"]["message_ts"],
            text = body["message"]["text"],
            attachments =  [{
                "blocks": [{
                    "type": "context",
                    "elements": [{
                        "type": "plain_text",
                        "text": "紀錄已刪除",
                        "emoji": True
                    }]
                }]
            }]
        )
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.action("showFile-1")
def handle_actionId_0(ack, say):
    ack()
    try:
        say("https://ibm.enterprise.slack.com/files/T4D2GQDRA/F028880B3QQ")
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.action("showFile-2")
def handle_actionId_2(ack, say):
    ack()
    try:
        say("https://ibm.enterprise.slack.com/files/T4D2GQDRA/F027X9F0F2M")
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.action("showFile-3")
def handle_actionId_3(ack):
    ack()

@app.action("showFile-4")
def handle_actionId_4(ack, say):
    ack()
    try:
        say("https://ibm.enterprise.slack.com/files/T4D2GQDRA/F02BDP60S6L")
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.message("")
def handle_any_message(say, ack, logger, message, client):
    ack()
    try:
        # say("不要亂跟我說話！")
        client.chat_postMessage(
            channel = message["user"],
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "上傳居家運動紀錄請直接上傳一張圖片、並跟據指示填寫相關資料。如要查詢其他 EWC 活動資訊，請上 <https://pages.github.ibm.com/EWC/ewc-health/index.html|居家健康月活動網站> 或 <https://w3.ibm.com/w3publisher/ewc-taiwan|EWC 官網>"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "使用教學",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": "click_me_123",
                        "action_id": "showFile-1"
                    }
                }
            ]
        )
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

@app.command("/ewc")
def handle_welcome_message(logger, command, ack, client):
    ack()
    try:
        client.chat_postMessage(
            channel =  command["user_id"],
            text = "上傳成功囉，本次上傳紀錄如下",
            blocks = [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "歡迎使用 EWC Taiwan 居家健康月ー每日運動紀錄照片上傳機器人！請上傳圖片給我，開始記錄運動紀錄，具體操作方式請閱讀以下指引，若有任何疑慮，請聯絡 EWC Admin <@U01M8FR6ADQ>"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "使用教學",
                            "emoji": True
                        },
                        "value": "click_me_123",
                        "action_id": "showFile-1"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "上傳規則與照片範例",
                            "emoji": True
                        },
                        "value": "click_me_123",
                        "action_id": "showFile-2"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "無效照片範例",
                            "emoji": True
                        },
                        "value": "click_me_123",
                        "action_id": "showFile-4"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Q&A",
                            "emoji": True
                        },
                        "value": "click_me_123",
                        "url": "https://pages.github.ibm.com/EWC/ewc-health/index.html#faq",
                        "action_id": "showFile-3"
                    }
                ]
            }]
        )
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

from flask import Flask, request

flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

@flask_app.route("/", methods=["POST","GET"])
def nothing():
    return ('', 204)

@flask_app.route("/slack/events", methods=["POST","GET"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    flask_app.run(host="0.0.0.0", port=port)
