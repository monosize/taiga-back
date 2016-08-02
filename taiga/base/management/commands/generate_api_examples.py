# -*- coding: utf-8 -*-
# Copyright (C) 2014-2016 Andrey Antukh <niwi@niwi.nz>
# Copyright (C) 2014-2016 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014-2016 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2014-2016 Alejandro Alonso <alejandro.alonso@kaleidos.net>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime

from jinja2 import Template
import json
import subprocess
import os

from optparse import make_option

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from taiga.base.mails import mail_builder

from taiga.projects.models import Project, Membership
from taiga.projects.history.models import HistoryEntry
from taiga.projects.history.services import get_history_queryset_by_model_instance

reqs = {
    "memberships-bulk-create": {
        "method": "POST",
        "url": "/api/v1/memberships/bulk_create",
        "body": {
            "project_id": 3,
            "bulk_memberships": [
                {"role_id": 10, "email": "test@test.com"},
                {"role_id": 12, "email": "john@doe.com"}
            ]
        }
    },
    "invitations-get": {
        "method": "GET",
        "url": "/api/v1/invitations/8e3af6bcd4"
    },
    "memberships-patch": {
        "method": "PATCH",
        "url": "/api/v1/memberships/1",
        "body": {
            "role": 10
        }
    },
    "memberships-create": {
        "method": "POST",
        "url": "/api/v1/memberships",
        "body": {
            "project": 3,
            "role": 12,
            "email": "test@test.com"
        }
    },
    "memberships-get": {
        "method": "GET",
        "url": "/api/v1/memberships/1",
    },
    "memberships-delete":{
        "method": "DELETE",
        "url": "/api/v1/memberships/1",
    },
    "memberships-resend-invitation": {
        "method": "POST",
        "url": "/api/v1/memberships/1/resend_invitation",
    },
    "memberships-list": {
        "method": "GET",
        "url": "/api/v1/memberships",
    },
    "project-memberships": {
        "method": "GET",
        "url": "/api/v1/memberships?project=1",
    },
    "register-user": {
        "method": "POST",
        "url": "/api/v1/auth/register",
        "body": {
            "type": "private",
            "existing": False,
            "token": "e8ea658e-6655-11e4-9d95-b499ba562790",
            "username": "'${USERNAME}'",
            "password": "'${PASSWORD}'",
            "email": "'${EMAIL}'",
            "full_name": "'${FULL_NAME}'"
        }
    },
    "github-login": {
        "method": "POST",
        "url": "/api/v1/auth",
        "body": {
            "type": "github",
            "code": "'${GITHUB_CODE}'"
        }
    },
    "normal-register": {
        "method": "POST",
        "url": "/api/v1/auth/register",
        "body": {
           "type": "public",
           "username": "'${USERNAME}'",
           "password": "'${PASSWORD}'",
           "email": "'${EMAIL}'",
           "full_name": "'${FULL_NAME}'"
        }
    },
    "normal-login": {
        "method": "POST",
        "url": "/api/v1/auth",
        "body": {
            "type": "normal",
            "username": "'${USERNAME}'",
            "password": "'${PASSWORD}'"
        }
    },
    "add-attachment-to-us": {
        "method": "MULTIPART-POST",
        "url": "/api/v1/userstories/attachments",
        "body": {
            "object_id": 81,
            "project": 3,
            "attached_file": "@/tmp/test.png"
        }
    },
    "unwatch": {
        "method": "POST",
        "url": "/api/v1/userstories/1/unwatch"
    },
    "user-stories-bulk-update-sprint-order": {
        "method": "POST",
        "url": "/api/v1/userstories/bulk_update_sprint_order",
        "body": {
           "project_id": 3,
           "bulk_stories": [
               {
                   "us_id": 123,
                   "order": 2
               },
               {
                   "us_id": 456,
                   "order": 2
               }
           ]
        }
    },
    "user-stories-bulk-create": {
        "method": "POST",
        "url": "/api/v1/userstories/bulk_create",
        "body": {
            "project_id": 3,
            "bulk_stories": "US 1 \n US 2 \n US 3"
        }
    },
    "user-stories-bulk-update-milestone": {
        "method": "POST",
        "url": "/api/v1/userstories/bulk_update_milestone",
        "body": {
            "project_id": 3,
            "milestone_id": 3,
            "bulk_stories": [
                {
                    "us_id": 123
                },
                {
                    "us_id": 456
                }
            ]
        }
    },
    "user-stories-patch": {
        "method": "PATCH",
        "url": "/api/v1/userstories/1",
        "body": {
            "subject": "Patching subject"
        }
    },
    "user-stories-create": {
        "method": "POST",
        "url": "/api/v1/userstories",
        "body": {
            "assigned_to": None,
            "backlog_order": 2,
            "blocked_note": "blocking reason",
            "client_requirement": False,
            "description": "Implement API CALL",
            "is_blocked": False,
            "is_closed": True,
            "kanban_order": 37,
            "milestone": None,
            "points": {
                "129": 361,
                "130": 361,
                "131": 361,
                "132": 364
            },
            "project": 3,
            "sprint_order": 2,
            "status": 13,
            "subject": "Customer personal data",
            "tags": [
                "service catalog",
                "customer"
            ],
            "team_requirement": False,
            "watchers": []
        }
    },
    "user-stories-simple-create": {
        "method": "POST",
        "url": "/api/v1/userstories",
        "body": {
            "project": 3,
            "subject": "Customer personal data"
        }
    },
    "user-stories-get": {
        "method": "GET",
        "url": "/api/v1/userstories/1",
    },
    "user-stories-filter-data": {
        "method": "GET",
        "url": "/api/v1/userstories/filters_data?project=1",
    },
    "user-stories-attachment-delete": {
        "method": "DELETE",
        "url": "/api/v1/userstories/attachments/415",
    },
    "user-stories-watch": {
        "method": "POST",
        "url": "/api/v1/userstories/1/watch",
    },
    "user-stories-delete": {
        "method": "DELETE",
        "url": "/api/v1/userstories/1",
    },
    "user-stories-get-voters": {
        "method": "GET",
        "url": "/api/v1/userstories/1/voters",
    },
    "user-stories-attachment-get": {
        "method": "GET",
        "url": "/api/v1/userstories/attachments?object_id=81\&project=3",
    },
    "user-stories-attachment-patch": {
        "method": "PATCH",
        "url": "/api/v1/userstories/attachments/417",
        "body": "description=patching description"
    },
    "user-stories-upvote": {
        "method": "POST",
        "url": "/api/v1/userstories/1/upvote",
    },
    "user-stories-list": {
        "method": "GET",
        "url": "/api/v1/userstories",
    },
    "user-stories-filtered-list": {
        "method": "GET",
        "url": "/api/v1/userstories?project=1",
    },
    "user-stories-downvote": {
        "method": "POST",
        "url": "/api/v1/userstories/1/downvote",
    },
    "user-stories-get-by-ref": {
        "method": "GET",
        "url": "/api/v1/userstories/by_ref?ref=1&project=1",
    },
    "user-stories-get-watchers": {
        "method": "GET",
        "url": "/api/v1/userstories/1/watchers",
    },
    "user-stories-attachments-list": {
        "method": "GET",
        "url": "/api/v1/userstories/attachments/415",
    },
    "user-stories-bulk-update-backlog-order": {
        "method": "POST",
        "url": "/api/v1/userstories/bulk_update_backlog_order",
        "body": {
            "project_id": 3,
            "bulk_stories": [
                {
                    "us_id": 123,
                    "order": 2
                },
                {
                    "us_id": 456,
                    "order": 2
                }
            ]
        }
    },
    "user-stories-bulk-update-kanban-order": {
        "method": "POST",
        "url": "/api/v1/userstories/bulk_update_kanban_order",
        "body": {
            "project_id": 3,
            "bulk_stories": [
                {
                    "us_id": 123,
                    "order": 2
                },
                {
                    "us_id": 456,
                    "order": 2
                }
            ]
        }
    },
    "projects-timeline-get": {
        "method": "GET",
        "url": "/api/v1/timeline/project/1",
    },
    "users-timeline-get": {
        "method": "GET",
        "url": "/api/v1/timeline/user/1",
    },
    "profile-timeline-get": {
        "method": "GET",
        "url": "/api/v1/timeline/profile/1",
    },
    "issue-statues-patch": {
        "method": "PATCH",
        "url": "/api/v1/issue-statuses/1",
        "body": {
            "name": "Patch status name"
        }
    },
    "issue-statuses-create": {
        "method": "POST",
        "url": "/api/v1/issue-statuses",
        "body": {
            "color": "#AAAAAA",
            "is_closed": True,
            "name": "New status",
            "order": 8,
            "project": 3
        }
    },
    "issue-statuses-simple-create": {
        "method": "POST",
        "url": "/api/v1/issue-statuses",
        "body": {
            "project": 3,
            "name": "New status name"
        }
    },
    "issue-statuses-get": {
        "method": "GET",
        "url": "/api/v1/issue-statuses/1",
    },
    "issue-statuses-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/issue-statuses/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_issue_statuses": [[1,10], [2,5]]
        }
    },
    "issue-statues-delete": {
        "method": "DELETE",
        "url": "/api/v1/issue-statuses/1",
    },
    "issue-statuses-list": {
        "method": "GET",
        "url": "/api/v1/issue-statuses",
    },
    "issue-statuses-filtered-list": {
        "method": "GET",
        "url": "/api/v1/issue-statuses?project=1",
    },
    "user-stories-custom-attributes-patch": {
        "method": "PATCH",
        "url": "/api/v1/userstory-custom-attributes/1",
        "body": {
            "name": "Duration"
        }
    },
    "user-stories-custom-attributes-create": {
        "method": "POST",
        "url": "/api/v1/userstory-custom-attributes",
        "body": {
            "name": "Duration",
            "description": "Duration in minutes",
            "order": 8,
            "project": 3
        }
    },
    "user-stories-custom-attributes-simple-create": {
        "method": "POST",
        "url": "/api/v1/userstory-custom-attributes",
        "body": {
            "name": "Duration",
            "project": 3
        }
    },
    "user-stories-custom-attributes-get": {
        "method": "GET",
        "url": "/api/v1/userstory-custom-attributes/1",
    },
    "user-stories-custom-attributes-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/userstory-custom-attributes/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_userstory_custom_attributes": [[1,10], [2,5]]
        }
    },
    "user-stories-custom-attributes-delete": {
        "method": "DELETE",
        "url": "/api/v1/userstory-custom-attributes/1",
    },
    "user-stories-custom-attributes-list": {
        "method": "GET",
        "url": "/api/v1/userstory-custom-attributes",
    },
    "user-stories-custom-attributes-filtered-list": {
        "method": "GET",
        "url": "/api/v1/userstory-custom-attributes?project=1",
    },
    "tasks-custom-attributes-values-patch": {
        "method": "PATCH",
        "url": "/api/v1/tasks/custom-attributes-values/1",
        "body": {
            "attributes_values": {"1": "240 min"},
            "version": 2
        }
    },
    "tasks-custom-attributes-values-get": {
        "method": "GET",
        "url": "/api/v1/tasks/custom-attributes-values/1",
    },
    "projects-export": {
        "method": "GET",
        "url": "/api/v1/exporter/1",
    },
    "projects-import": {
        "method": "MULTIPART-POST",
        "url": "/api/v1/importer/load_dump",
        "body": {
            "dump": "@my-dump-file.json"
        }
    },
    "severities-patch": {
        "method": "PATCH",
        "url": "/api/v1/severities/1",
        "body": {
            "name": "Patch name"
        }
    },
    "severities-create": {
        "method": "POST",
        "url": "/api/v1/severities",
        "body": {
            "color": "#AAAAAA",
            "name": "New severity",
            "order": 8,
            "project": 3
        }
    },
    "severities-simple-create": {
        "method": "POST",
        "url": "/api/v1/severities",
        "body": {
            "project": 3,
            "name": "New severity name"
        }
    },
    "severities-get": {
        "method": "GET",
        "url": "/api/v1/severities/1",
    },
    "severities-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/severities/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_severities": [[1,10], [2,5]]
        }
    },
    "severities-delete": {
        "method": "DELETE",
        "url": "/api/v1/severities/1",
    },
    "severities-list": {
        "method": "GET",
        "url": "/api/v1/severities",
    },
    "severities-filtered-list": {
        "method": "GET",
        "url": "/api/v1/severities?project=1",
    },
    "user-stories-edit-comment": {
        "method": "POST",
        "url": "/api/v1/history/userstory/1/edit_comment?id=10",
        "body": {
            "comment": "comment edition"
        }
    },
    "user-stories-get-comment-versions": {
        "method": "GET",
        "url": "/api/v1/history/userstory/1/comment_versions?id=10",
    },
    "user-story-delete-comment": {
        "method": "POST",
        "url": "/api/v1/history/userstory/1/delete_comment?id=10",
    },
    "user-stories-get-history": {
        "method": "GET",
        "url": "/api/v1/history/userstory/1",
    },
    "user-stories-undelete-comment": {
        "method": "POST",
        "url": "/api/v1/history/userstory/1/undelete_comment?id=10",
    },
    "task-statuses-patch": {
        "method": "PATCH",
        "url": "/api/v1/task-statuses/1",
        "body": {
            "name": "Patch status name"
        }
    },
    "task-statuses-create": {
        "method": "POST",
        "url": "/api/v1/task-statuses",
        "body": {
            "color": "#AAAAAA",
            "is_closed": True,
            "name": "New status",
            "order": 8,
            "project": 3
        }
    },
    "task-statuses-simple-create": {
        "method": "POST",
        "url": "/api/v1/task-statuses",
        "body": {
            "project": 3,
            "name": "New status name"
        }
    },
    "task-statuses-get": {
        "method": "GET",
        "url": "/api/v1/task-statuses/1",
    },
    "task-statuses-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/task-statuses/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_task_statuses": [[1,10], [2,5]]
        }
    },
    "task-statuses-delete": {
        "method": "DELETE",
        "url": "/api/v1/task-statuses/1",
    },
    "task-statuses-list": {
        "method": "GET",
        "url": "/api/v1/task-statuses",
    },
    "task-statuses-filtered-list": {
        "method": "GET",
        "url": "/api/v1/task-statuses?project=1",
    },
    "issues-attachments-create": {
        "method": "MULTIPART-POST",
        "url": "/api/v1/issues/attachments",
        "body": {
            "object_id": 81,
            "project": 3,
            "attached_file": "@/tmp/test.png"
        }
    },
    "issues-unwatch": {
        "method": "POST",
        "url": "/api/v1/issues/1/unwatch",
    },
    "issues-bulk-create": {
        "method": "POST",
        "url": "/api/v1/issues/bulk_create",
        "body": {
            "project_id": 3,
            "bulk_issues": "Issue 1 \n Issue 2 \n Issue 3"
        }
    },
    "issues-patch": {
        "method": "PATCH",
        "url": "/api/v1/issues/1",
        "body": {
            "subject": "Patching subject"
        }
    },
    "issues-create": {
        "method": "POST",
        "url": "/api/v1/issues",
        "body": {
            "assigned_to": None,
            "blocked_note": "blocking reason",
            "description": "Implement API CALL",
            "is_blocked": False,
            "is_closed": True,
            "milestone": None,
            "project": 3,
            "status": 13,
            "severity": 2,
            "priority": 3,
            "type": 1,
            "subject": "Customer personal data",
            "tags": [
                "service catalog",
                "customer"
            ],
            "watchers": []
        }
    },
    "issues-simple-create": {
        "method": "POST",
        "url": "/api/v1/issues",
        "body": {
            "project": 3,
            "subject": "Customer personal data"
        }
    },
    "issues-get": {
        "method": "GET",
        "url": "/api/v1/issues/1",
    },
    "issues-filters-data-get": {
        "method": "GET",
        "url": "/api/v1/issues/filters_data?project=1",
    },
    "issues-attachment-delete": {
        "method": "DELETE",
        "url": "/api/v1/issues/attachments/415",
    },
    "issues-watch": {
        "method": "POST",
        "url": "/api/v1/issues/1/watch",
    },
    "issues-delete": {
        "method": "DELETE",
        "url": "/api/v1/issues/1",
    },
    "issues-voters": {
        "method": "GET",
        "url": "/api/v1/issues/1/voters",
    },
    "issues-attachment-get": {
        "method": "GET",
        "url": "/api/v1/issues/attachments?object_id=81\&project=3",
    },
    "issues-attachment-patch": {
        "method": "PATCH",
        "url": "/api/v1/issues/attachments/417",
    },
    "issues-upvote": {
        "method": "POST",
        "url": "/api/v1/issues/1/upvote",
    },
    "issues-list": {
        "method": "GET",
        "url": "/api/v1/issues",
    },
    "issues-filtered-list": {
        "method": "GET",
        "url": "/api/v1/issues?project=1",
    },
    "issues-filtered-and-ordered-list": {
        "method": "GET",
        "url": "/api/v1/issues?project=1\&order_by=priority",
    },
    "issues-downvote": {
        "method": "POST",
        "url": "/api/v1/issues/1/downvote",
    },
    "issues-get-by-ref": {
        "method": "GET",
        "url": "/api/v1/issues/by_ref?ref=1&project=1",
    },
    "issues-watchers": {
        "method": "GET",
        "url": "/api/v1/issues/1/watchers",
    },
    "issues-attachment-get-by-id": {
        "method": "GET",
        "url": "/api/v1/issues/attachments/415",
    },
    "priorities-patch": {
        "method": "PATCH",
        "url": "/api/v1/priorities/1",
        "body": {
            "name": "Patch name"
        }
    },
    "priorities-create": {
        "method": "POST",
        "url": "/api/v1/priorities",
        "body": {
            "color": "#AAAAAA",
            "name": "New priority",
            "order": 8,
            "project": 3
        }
    },
    "priorities-simple-create": {
        "method": "POST",
        "url": "/api/v1/priorities",
        "body": {
            "project": 3,
            "name": "New priority name"
        }
    },
    "priorities-get": {
        "method": "GET",
        "url": "/api/v1/priorities/1",
    },
    "priorities-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/priorities/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_priorities": [[1,10], [2,5]]
        }
    },
    "priorities-delete": {
        "method": "DELETE",
        "url": "/api/v1/priorities/1",
    },
    "priorities-list": {
        "method": "GET",
        "url": "/api/v1/priorities",
    },
    "priorities-filtered-list": {
        "method": "GET",
        "url": "/api/v1/priorities?project=1",
    },
    "webhooklogs-list": {
        "method": "GET",
        "url": "/api/v1/webhooklogs",
    },
    "webhooklogs-filtered-list": {
        "method": "GET",
        "url": "/api/v1/webhooklogs?webhook=1",
    },
    "webhooks-test": {
        "method": "GET",
        "url": "/api/v1/webhooks/1/test",
    },
    "webhooks-patch": {
        "method": "PATCH",
        "url": "/api/v1/webhooks/1",
        "body": {
            "name": "My service name"
        }
    },
    "webhooks-create": {
        "method": "POST",
        "url": "/api/v1/webhooks",
        "body": {
            "project": 1,
            "name": "My service webhook",
            "url": "http://myservice.com/webhooks",
            "key": "my-very-secret-key"
        }
    },
    "webhooks-get": {
        "method": "GET",
        "url": "/api/v1/webhooks/1",
    },
    "webhooklogs-get": {
        "method": "GET",
        "url": "/api/v1/webhooklogs/1",
    },
    "webhooks-delete": {
        "method": "DELETE",
        "url": "/api/v1/webhooks/1",
    },
    "webhooks-list": {
        "method": "GET",
        "url": "/api/v1/webhooks",
    },
    "webhooks-filtered-list": {
        "method": "GET",
        "url": "/api/v1/webhooks?project=1",
    },
    "webhooklogs-resend": {
        "method": "GET",
        "url": "/api/v1/webhooklogs/1/resend",
    },
    "notify-policies-patch": {
        "method": "PATCH",
        "url": "/api/v1/notify-policies/1",
        "body": {
          "notify_level": 2
        }
    },
    "notify-policies-get": {
        "method": "GET",
        "url": "/api/v1/notify-policies/1",
    },
    "notify-policies-list": {
        "method": "GET",
        "url": "/api/v1/notify-policies",
    },
    "issues-custom-attributs-values-patch": {
        "method": "PATCH",
        "url": "/api/v1/issues/custom-attributes-values/1",
        "body": {
            "attributes_values": {"1": "240 min"},
            "version": 2
        }
    },
    "issues-custom-attributes-values-get": {
        "method": "GET",
        "url": "/api/v1/issues/custom-attributes-values/1",
    },
    "stats-discover": {
        "method": "GET",
        "url": "/api/v1/stats/discover",
    },
    "stats-system": {
        "method": "GET",
        "url": "/api/v1/stats/system",
    },
    "user-storage-patch": {
        "method": "PATCH",
        "url": "/api/v1/user-storage/favorite-forest",
        "body": {
            "value": "Russian Taiga"
        }
    },
    "user-storage-create": {
        "method": "POST",
        "url": "/api/v1/user-storage",
        "body": {
            "key": "favorite-forest",
            "value": "Taiga"
        }
    },
    "user-storage-get": {
        "method": "GET",
        "url": "/api/v1/user-storage/favorite-forest",
    },
    "user-storage-delete": {
        "method": "DELETE",
        "url": "/api/v1/user-storage/favorite-forest",
    },
    "user-storage-list": {
        "method": "GET",
        "url": "/api/v1/user-storage",
    },
    "projects-unwatch": {
        "method": "POST",
        "url": "/api/v1/projects/1/unwatch",
    },
    "projects-create-template": {
        "method": "POST",
        "url": "/api/v1/projects/1/create_template",
        "body": {
            "template_name": "Beta template",
            "template_description": "Beta template description"
        }
    },
    "projects-transfer-request": {
        "method": "POST",
        "url": "/api/v1/projects/1/transfer_request",
    },
    "projects-stats": {
        "method": "GET",
        "url": "/api/v1/projects/1/stats",
    },
    "projects-change-logo": {
        "method": "POST",
        "url": "/api/v1/projects/1/change_logo",
    },
    "projeces-leave": {
        "method": "POST",
        "url": "/api/v1/projects/1/leave",
    },
    "projects-issues-stats": {
        "method": "GET",
        "url": "/api/v1/projects/1/issues_stats",
    },
    "projects-update": {
        "method": "PUT",
        "url": "/api/v1/projects/1",
        "body": {
            "name": "Beta project put",
            "description": "Beta description"
        }
    },
    "projects-patch": {
        "method": "PATCH",
        "url": "/api/v1/projects/1",
        "body": {
            "name": "Beta project patch"
        }
    },
    "projects-simple-create": {
        "method": "POST",
        "url": "/api/v1/projects",
        "body": {
            "name": "Beta project",
            "description": "Beta description"
        }
    },
    "projects-create": {
        "method": "-X POST",
        "url": "/api/v1/projects",
        "body": {
            "name": "Beta project",
            "description": "Taiga",
            "creation_template": 1,
            "is_backlog_activated": False,
            "is_issues_activated": True,
            "is_kanban_activated": True,
            "is_private": False,
            "is_wiki_activated": True,
            "videoconferences": "appear-in",
            "videoconferences_extra_data": None,
            "total_milestones": 3,
            "total_story_points": 20.0
        }
    },
    "projects-get": {
        "method": "GET",
        "url": "/api/v1/projects/1",
    },
    "projects-watch": {
        "method": "POST",
        "url": "/api/v1/projects/1/watch",
        "body": {
            "notify_level": 3
        }
    },
    "projects-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/projects/bulk_update_order",
        "body": [
            {
                "project_id": 123,
                "order": 2
            },
            {
                "project_id": 456,
                "order": 2
            }
        ]
    },
    "projects-unlike": {
        "method": "POST",
        "url": "/api/v1/projects/1/unlike",
    },
    "projects-tags-colors": {
        "method": "GET",
        "url": "/api/v1/projects/1/tags_colors",
    },
    "projects-get-by-slug": {
        "method": "GET",
        "url": "/api/v1/projects/by_slug?slug=test",
    },
    "projects-delete": {
        "method": "DELETE",
        "url": "/api/v1/projects/1",
    },
    "projects-modules-get": {
        "method": "GET",
        "url": "/api/v1/projects/1/modules",
    },
    "projects-fans": {
        "method": "GET",
        "url": "/api/v1/projects/1/fans",
    },
    "projects-transfer-validate-token": {
        "method": "POST",
        "url": "/api/v1/projects/1/transfer_validate_token",
        "body": {
            "token": "'${TRANSFER_TOKEN}'",
        }
    },
    "projects-list": {
        "method": "GET",
        "url": "/api/v1/projects",
    },
    "projects-filtered-list": {
        "method": "GET",
        "url": "/api/v1/projects?member=1",
    },
    "projects-filtered-and-ordered-list": {
        "method": "GET",
        "url": "/api/v1/projects?member=1&order_by=memberships__user_order",
    },
    "project-modules-patch": {
        "method": "PATCH",
        "url": "/api/v1/projects/1/modules",
        "body": {
            "github": {
                "secret": "new_secret"
            }
        }
    },
    "projects-start-tranfer": {
        "method": "POST",
        "url": "/api/v1/projects/1/transfer_start",
        "body": {
            "user": "'${USER_ID}'",
        }
    },
    "projects-unlike": {
        "method": "POST",
        "url": "/api/v1/projects/1/like",
    },
    "projects-watchers": {
        "method": "GET",
        "url": "/api/v1/projects/1/watchers",
    },
    "projects-transfer-accept": {
        "method": "POST",
        "url": "/api/v1/projects/1/transfer_accept",
        "body": {
            "token": "'${TRANSFER_TOKEN}'",
            "reason": "testing"
        }
    },
    "projects-remove-logo": {
        "method": "POST",
        "url": "/api/v1/projects/1/remove_logo",
    },
    "projects-transfer-reject": {
        "method": "POST",
        "url": "/api/v1/projects/1/transfer_reject",
        "body": {
            "token": "'${TRANSFER_TOKEN}'",
            "reason": "testing"
        }
    },
    "issue-types-patch": {
        "method": "PATCH",
        "url": "/api/v1/issue-types/1",
        "body": {
          "name": "Patch type name"
        }
    },
    "issue-types-create": {
        "method": "POST",
        "url": "/api/v1/issue-types",
        "body": {
            "color": "#AAAAAA",
            "name": "New type",
            "order": 8,
            "project": 3
        }
    },
    "issue-types-simple-create": {
        "method": "POST",
        "url": "/api/v1/issue-types",
        "body": {
            "project": 3,
            "name": "New type name"
        }
    },
    "issue-types-get": {
        "method": "GET",
        "url": "/api/v1/issue-types/1",
    },
    "issue-types-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/issue-types/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_issue_types": [[1,10], [2,5]]
        }
    },
    "issue-types-delete": {
        "method": "DELETE",
        "url": "/api/v1/issue-types/1",
    },
    "issue-types-list": {
        "method": "GET",
        "url": "/api/v1/issue-types",
    },
    "issue-types-filtered-list": {
        "method": "GET",
        "url": "/api/v1/issue-types?project=1",
    },
    "wiki-attachments-create": {
        "method": "MULTIPART-POST",
        "url": "/api/v1/wiki/attachments",
        "body": {
            "object_id": 81,
            "project": 3,
            "attached_file": "@/tmp/test.png"
        }
    },
    "wiki-unwatch": {
        "method": "POST",
        "url": "/api/v1/wiki/1/unwatch",
    },
    "wiki-patch": {
        "method": "PATCH",
        "url": "/api/v1/wiki/1",
        "body": {
          "subject": "Patching subject"
        }
    },
    "wiki-create": {
        "method": "POST",
        "url": "/api/v1/wiki",
        "body": {
            "project": 1,
            "slug": "home",
            "content": "Lorem ipsum dolor.",
            "watchers": []
        }
    },
    "wiki-create": {
        "method": "POST",
        "url": "/api/v1/wiki",
        "body": {
            "project": 1,
            "slug": "home",
            "content": "Lorem ipsum dolor."
        }
    },
    "wiki-get": {
        "method": "GET",
        "url": "/api/v1/wiki/1",
    },
    "wiki-attachments-delete": {
        "method": "DELETE",
        "url": "/api/v1/wiki/attachments/415",
    },
    "wiki-watch": {
        "method": "POST",
        "url": "/api/v1/wiki/1/watch",
    },
    "wiki-get-by-slug": {
        "method": "GET",
        "url": "/api/v1/wiki/by_slug?slug=home\&project=1",
    },
    "wiki-delete": {
        "method": "DELETE",
        "url": "/api/v1/wiki/1",
    },
    "wiki-attachments-get": {
        "method": "GET",
        "url": "/api/v1/wiki/attachments?object_id=81\&project=3",
    },
    "wiki-attachments-patch": {
        "method": "PATCH",
        "url": "/api/v1/wiki/attachments/417",
    },
    "wiki-list": {
        "method": "GET",
        "url": "/api/v1/wiki",
    },
    "wiki-filtered-list": {
        "method": "GET",
        "url": "/api/v1/wiki?project=1",
    },
    "wiki-watchers": {
        "method": "GET",
        "url": "/api/v1/wiki/1/watchers",
    },
    "wiki-attachments-get": {
        "method": "GET",
        "url": "/api/v1/wiki/attachments/415",
    },
    "feedback": {
        "method": "POST",
        "url": "/api/v1/feedback",
        "body": {
            "comment": "Testing feedback"
        }
    },
    "wiki-links-patch": {
        "method": "PATCH",
        "url": "/api/v1/wiki-links/1",
        "body": {
            "subject": "Patching subject"
        }
    },
    "wiki-links-create": {
        "method": "POST",
        "url": "/api/v1/wiki-links",
        "body": {
            "project": 1,
            "title": "Home page",
            "href": "home",
            "order": 1
        }
    },
    "wiki-links-simple-create": {
        "method": "POST",
        "url": "/api/v1/wiki-links",
        "body": {
            "project": 1,
            "title": "Home page",
            "href": "home"
        }
    },
    "wiki-links-get": {
        "method": "GET",
        "url": "/api/v1/wiki-links/1",
    },
    "wiki-links-create": {
        "method": "DELETE",
        "url": "/api/v1/wiki-links/1",
    },
    "wiki-links-list": {
        "method": "GET",
        "url": "/api/v1/wiki-links",
    },
    "wiki-links-filtered-list": {
        "method": "GET",
        "url": "/api/v1/wiki-links?project=1",
    },
    "issues-custom-attributes-patch": {
        "method": "PATCH",
        "url": "/api/v1/issue-custom-attributes/1",
        "body": {
            "name": "Duration"
        }
    },
    "issues-custom-attributes-create": {
        "method": "POST",
        "url": "/api/v1/issue-custom-attributes",
        "body": {
            "name": "Duration",
            "description": "Duration in minutes",
            "order": 8,
            "project": 3
        }
    },
    "issues-custom-attributes-simple-create": {
        "method": "POST",
        "url": "/api/v1/issue-custom-attributes",
        "body": {
            "name": "Duration",
            "project": 3
        }
    },
    "issues-custom-attributes-get": {
        "method": "GET",
        "url": "/api/v1/issue-custom-attributes/1",
    },
    "issues-custom-attributes-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/issue-custom-attributes/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_issue_custom_attributes": [[1,10], [2,5]]
        }
    },
    "issue-custom-attributes-delete": {
        "method": "DELETE",
        "url": "/api/v1/issue-custom-attributes/1",
    },
    "issue-custom-attributes-list": {
        "method": "GET",
        "url": "/api/v1/issue-custom-attributes",
    },
    "issue-custom-attributes-filtered-list": {
        "method": "GET",
        "url": "/api/v1/issue-custom-attributes?project=1",
    },
    "user-story-statuses-patch": {
        "method": "PATCH",
        "url": "/api/v1/userstory-statuses/1",
        "body": {
            "name": "Patch status name"
        }
    },
    "user-story-statuses-create": {
        "method": "POST",
        "url": "/api/v1/userstory-statuses",
        "body": {
            "color": "#AAAAAA",
            "is_closed": True,
            "name": "New status",
            "order": 8,
            "project": 3,
            "wip_limit": 6
        }
    },
    "user-story-statuses-simple-create": {
        "method": "POST",
        "url": "/api/v1/userstory-statuses",
        "body": {
            "project": 3,
            "name": "New status name"
        }
    },
    "user-story-statuses-get": {
        "method": "GET",
        "url": "/api/v1/userstory-statuses/1",
    },
    "user-story-statuses-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/userstory-statuses/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_userstory_statuses": [[1,10], [2,5]]
        }
    },
    "user-story-statuses-delete": {
        "method": "DELETE",
        "url": "/api/v1/userstory-statuses/1",
    },
    "user-story-statuses-list": {
        "method": "GET",
        "url": "/api/v1/userstory-statuses",
    },
    "user-story-statuses-filtered-list": {
        "method": "GET",
        "url": "/api/v1/userstory-statuses?project=1",
    },
    "tasks-attachments-create": {
        "method": "MULTIPART-POST",
        "url": "/api/v1/tasks/attachments",
        "body": {
            "object_id": 81,
            "project": 3,
            "attached_file": "@/tmp/test.png"
        }
    },
    "tasks-unwatch": {
        "method": "POST",
        "url": "/api/v1/tasks/1/unwatch",
    },
    "tasks-bulk-create": {
        "method": "POST",
        "url": "/api/v1/tasks/bulk_create",
        "body": {
            "project_id": 3,
            "bulk_tasks": "Task 1 \n Task 2 \n Task 3"
        }
    },
    "tasks-patch": {
        "method": "PATCH",
        "url": "/api/v1/tasks/1",
        "body": {
            "subject": "Patching subject"
        }
    },
    "tasks-create": {
        "method": "POST",
        "url": "/api/v1/tasks",
        "body": {
            "assigned_to": None,
            "blocked_note": "blocking reason",
            "description": "Implement API CALL",
            "is_blocked": False,
            "is_closed": True,
            "milestone": None,
            "project": 3,
            "user_story": 17,
            "status": 13,
            "subject": "Customer personal data",
            "tags": [
                "service catalog",
                "customer"
            ],
            "us_order": 1,
            "taskboard_order": 1,
            "is_iocaine": False,
            "external_reference": None,
            "watchers": []
        }
    },
    "tasks-simple-create": {
        "method": "POST",
        "url": "/api/v1/tasks",
        "body": {
            "project": 3,
            "subject": "Customer personal data"
        }
    },
    "tasks-get": {
        "method": "GET",
        "url": "/api/v1/tasks/1",
    },
    "tasks-filters-data": {
        "method": "GET",
        "url": "/api/v1/tasks/filters_data?project=1",
    },
    "tasks-attachments-delete": {
        "method": "DELETE",
        "url": "/api/v1/tasks/attachments/415",
    },
    "tasks-watch": {
        "method": "POST",
        "url": "/api/v1/tasks/1/watch",
    },
    "tasks-delete": {
        "method": "DELETE",
        "url": "/api/v1/tasks/1",
    },
    "tasks-voters": {
        "method": "GET",
        "url": "/api/v1/tasks/1/voters",
    },
    "tasks-attachments-get": {
        "method": "GET",
        "url": "/api/v1/tasks/attachments?object_id=81\&project=3",
    },
    "tasks-attachments-patch": {
        "method": "PATCH",
        "url": "/api/v1/tasks/attachments/417",
    },
    "tasks-upvote": {
        "method": "POST",
        "url": "/api/v1/tasks/1/upvote",
    },
    "tasks-list": {
        "method": "GET",
        "url": "/api/v1/tasks",
    },
    "tasks-filtered-list": {
        "method": "GET",
        "url": "/api/v1/tasks?project=1",
    },
    "tasks-downvote": {
        "method": "POST",
        "url": "/api/v1/tasks/1/downvote",
    },
    "tasks-by-ref": {
        "method": "GET",
        "url": "/api/v1/tasks/by_ref?ref=1&project=1",
    },
    "tasks-watchers": {
        "method": "GET",
        "url": "/api/v1/tasks/1/watchers",
    },
    "tasks-attachments-get": {
        "method": "GET",
        "url": "/api/v1/tasks/attachments/415",
    },
    "applications-get": {
        "method": "GET",
        "url": "/api/v1/applications/5c8515c2-4fc4-11e5-9a5e-68f72800aadd/token",
    },
    "application-tokens-authorize": {
        "method": "POST",
        "url": "/api/v1/application-tokens/authorize",
        "body": {
            "application": "a60c3208-5234-11e5-96df-68f72800aadd",
            "state": "random-state"
        }
    },
    "application-tokens-validate": {
        "method": "POST",
        "url": "/api/v1/application-tokens/validate",
        "body": {
            "application": "a60c3208-5234-11e5-96df-68f72800aadd",
            "auth_code": "21ce08c4-5237-11e5-a8a3-68f72800aadd",
            "state": "random-state"
        }
    },
    "project-templates-patch": {
        "method": "PATCH",
        "url": "/api/v1/project-templates/1",
        "body": {
            "description": "New description"
        }
    },
    "project-templates-create": {
        "method": "POST",
        "url": "/api/v1/project-templates",
        "body": {
            "default_options": {
                "us_status": "New",
                "points": "?",
                "priority": "Normal",
                "severity": "Normal",
                "task_status": "New",
                "issue_type": "Bug",
                "issue_status": "New"
            },
            "us_statuses": [
                {
                    "wip_limit": None,
                    "color": "#999999",
                    "name": "New",
                    "order": 1,
                    "is_closed": False
                },
                {
                    "wip_limit": None,
                    "color": "#f57900",
                    "name": "Ready",
                    "order": 2,
                    "is_closed": False
                },
                {
                    "wip_limit": None,
                    "color": "#729fcf",
                    "name": "In progress",
                    "order": 3,
                    "is_closed": False
                },
                {
                    "wip_limit": None,
                    "color": "#4e9a06",
                    "name": "Ready for test",
                    "order": 4,
                    "is_closed": False
                },
                {
                    "wip_limit": None,
                    "color": "#cc0000",
                    "name": "Done",
                    "order": 5,
                    "is_closed": True
                }
            ],
            "points": [
                {
                    "value": None,
                    "name": "?",
                    "order": 1
                },
                {
                    "value": 0.0,
                    "name": "0",
                    "order": 2
                },
                {
                    "value": 0.5,
                    "name": "1/2",
                    "order": 3
                },
                {
                    "value": 1.0,
                    "name": "1",
                    "order": 4
                },
                {
                    "value": 2.0,
                    "name": "2",
                    "order": 5
                },
                {
                    "value": 3.0,
                    "name": "3",
                    "order": 6
                },
                {
                    "value": 5.0,
                    "name": "5",
                    "order": 7
                },
                {
                    "value": 8.0,
                    "name": "8",
                    "order": 8
                },
                {
                    "value": 10.0,
                    "name": "10",
                    "order": 9
                },
                {
                    "value": 15.0,
                    "name": "15",
                    "order": 10
                },
                {
                    "value": 20.0,
                    "name": "20",
                    "order": 11
                },
                {
                    "value": 40.0,
                    "name": "40",
                    "order": 12
                }
            ],
            "task_statuses": [
                {
                    "color": "#999999",
                    "name": "New",
                    "order": 1,
                    "is_closed": False
                },
                {
                    "color": "#729fcf",
                    "name": "In progress",
                    "order": 2,
                    "is_closed": False
                },
                {
                    "color": "#f57900",
                    "name": "Ready for test",
                    "order": 3,
                    "is_closed": True
                },
                {
                    "color": "#4e9a06",
                    "name": "Closed",
                    "order": 4,
                    "is_closed": True
                },
                {
                    "color": "#cc0000",
                    "name": "Needs Info",
                    "order": 5,
                    "is_closed": False
                }
            ],
            "issue_statuses": [
                {
                    "color": "#999999",
                    "name": "New",
                    "order": 1,
                    "is_closed": False
                },
                {
                    "color": "#729fcf",
                    "name": "In progress",
                    "order": 2,
                    "is_closed": False
                },
                {
                    "color": "#f57900",
                    "name": "Ready for test",
                    "order": 3,
                    "is_closed": True
                },
                {
                    "color": "#4e9a06",
                    "name": "Closed",
                    "order": 4,
                    "is_closed": True
                },
                {
                    "color": "#cc0000",
                    "name": "Needs Info",
                    "order": 5,
                    "is_closed": False
                },
                {
                    "color": "#d3d7cf",
                    "name": "Rejected",
                    "order": 6,
                    "is_closed": True
                },
                {
                    "color": "#75507b",
                    "name": "Postponed",
                    "order": 7,
                    "is_closed": False
                }
            ],
            "issue_types": [
                {
                    "color": "#cc0000",
                    "name": "Bug",
                    "order": 1
                },
                {
                    "color": "#729fcf",
                    "name": "Question",
                    "order": 2
                },
                {
                    "color": "#4e9a06",
                    "name": "Enhancement",
                    "order": 3
                }
            ],
            "priorities": [
                {
                    "color": "#999999",
                    "name": "Low",
                    "order": 1
                },
                {
                    "color": "#4e9a06",
                    "name": "Normal",
                    "order": 3
                },
                {
                    "color": "#CC0000",
                    "name": "High",
                    "order": 5
                }
            ],
            "severities": [
                {
                    "color": "#999999",
                    "name": "Wishlist",
                    "order": 1
                },
                {
                    "color": "#729fcf",
                    "name": "Minor",
                    "order": 2
                },
                {
                    "color": "#4e9a06",
                    "name": "Normal",
                    "order": 3
                },
                {
                    "color": "#f57900",
                    "name": "Important",
                    "order": 4
                },
                {
                    "color": "#CC0000",
                    "name": "Critical",
                    "order": 5
                }
            ],
            "roles": [
                {
                    "permissions": [
                        "add_issue", "modify_issue", "comment_issue", "delete_issue",
                        "view_issues", "add_milestone", "modify_milestone",
                        "delete_milestone", "view_milestones", "view_project",
                        "add_task", "modify_task", "comment_task", "delete_task", "view_tasks",
                        "add_us", "modify_us", "comment_us", "delete_us", "view_us",
                        "add_wiki_page", "modify_wiki_page", "comment_wiki_page", "delete_wiki_page",
                        "view_wiki_pages", "add_wiki_link", "delete_wiki_link",
                        "view_wiki_links"
                    ],
                    "order": 10,
                    "computable": True,
                    "slug": "ux",
                    "name": "UX"
                },
                {
                    "permissions": [
                        "add_issue", "modify_issue", "comment_issue", "delete_issue",
                        "view_issues", "add_milestone", "modify_milestone",
                        "delete_milestone", "view_milestones", "view_project",
                        "add_task", "modify_task", "comment_task", "delete_task", "view_tasks",
                        "add_us", "modify_us", "comment_us", "delete_us", "view_us",
                        "add_wiki_page", "modify_wiki_page", "comment_wiki_page", "delete_wiki_page",
                        "view_wiki_pages", "add_wiki_link", "delete_wiki_link",
                        "view_wiki_links"
                    ],
                    "order": 20,
                    "computable": True,
                    "slug": "design",
                    "name": "Design"
                },
                {
                    "permissions": [
                        "add_issue", "modify_issue", "comment_issue", "delete_issue",
                        "view_issues", "add_milestone", "modify_milestone",
                        "delete_milestone", "view_milestones", "view_project",
                        "add_task", "modify_task", "comment_task", "delete_task", "view_tasks",
                        "add_us", "modify_us", "comment_us", "delete_us", "view_us",
                        "add_wiki_page", "modify_wiki_page", "comment_wiki_page", "delete_wiki_page",
                        "view_wiki_pages", "add_wiki_link", "delete_wiki_link",
                        "view_wiki_links"
                    ],
                    "order": 30,
                    "computable": True,
                    "slug": "front",
                    "name": "Front"
                },
                {
                    "permissions": [
                        "add_issue", "modify_issue", "comment_issue", "delete_issue",
                        "view_issues", "add_milestone", "modify_milestone",
                        "delete_milestone", "view_milestones", "view_project",
                        "add_task", "modify_task", "comment_task", "delete_task", "view_tasks",
                        "add_us", "modify_us", "comment_us", "delete_us", "view_us",
                        "add_wiki_page", "modify_wiki_page", "comment_wiki_page", "delete_wiki_page",
                        "view_wiki_pages", "add_wiki_link", "delete_wiki_link",
                        "view_wiki_links"
                    ],
                    "order": 40,
                    "computable": True,
                    "slug": "back",
                    "name": "Back"
                },
                {
                    "permissions": [
                        "add_issue", "modify_issue", "comment_issue", "delete_issue",
                        "view_issues", "add_milestone", "modify_milestone",
                        "delete_milestone", "view_milestones", "view_project",
                        "add_task", "modify_task", "comment_task", "delete_task", "view_tasks",
                        "add_us", "modify_us", "comment_us", "delete_us", "view_us",
                        "add_wiki_page", "modify_wiki_page", "comment_wiki_page", "delete_wiki_page",
                        "view_wiki_pages", "add_wiki_link", "delete_wiki_link",
                        "view_wiki_links"
                    ],
                    "order": 50,
                    "computable": False,
                    "slug": "product-owner",
                    "name": "Product Owner"
                },
                {
                    "permissions": [
                        "add_issue", "modify_issue", "comment_issue", "delete_issue",
                        "view_issues", "view_milestones", "view_project",
                        "view_tasks", "view_us", "modify_wiki_page", "comment_wiki_page",
                        "view_wiki_pages", "add_wiki_link", "delete_wiki_link",
                        "view_wiki_links"
                    ],
                    "order": 60,
                    "computable": False,
                    "slug": "stakeholder",
                    "name": "Stakeholder"
                }
            ],
            "id": 2,
            "name": "Kanban",
            "slug": "kanban",
            "description": "Sample description",
            "default_owner_role": "product-owner",
            "is_backlog_activated": False,
            "is_kanban_activated": True,
            "is_wiki_activated": False,
            "is_issues_activated": False,
            "videoconferences": None,
            "videoconferences_extra_data": ""
        }
    },
    "project-templates-simple-create": {
        "method": "POST",
        "url": "/api/v1/project-templates",
        "body": {
            "name": "Kanban",
            "description": "Sample description",
            "default_owner_role": "product-owner"
        }
    },
    "project-templates-get": {
        "method": "GET",
        "url": "/api/v1/project-templates/1",
    },
    "project-templates-delete": {
        "method": "DELETE",
        "url": "/api/v1/project-templates/1",
    },
    "project-templates-list": {
        "method": "GET",
        "url": "/api/v1/project-templates",
    },
    "project-templates-filtered-list": {
        "method": "GET",
        "url": "/api/v1/search?project=1\&text=design",
    },
    "points-patch": {
        "method": "PATCH",
        "url": "/api/v1/points/1",
        "body": {
            "name": "Patch name"
        }
    },
    "points-create": {
        "method": "POST",
        "url": "/api/v1/points",
        "body": {
            "color": "#AAAAAA",
            "name": "Huge",
            "order": 8,
            "value": 40,
            "project": 3
        }
    },
    "points-simple-create": {
        "method": "POST",
        "url": "/api/v1/points",
        "body": {
            "project": 3,
            "name": "Very huge"
        }
    },
    "points-get": {
        "method": "GET",
        "url": "/api/v1/points/1",
    },
    "points-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/points/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_points": [[1,10], [2,5]]
        }
    },
    "points-delete": {
        "method": "DELETE",
        "url": "/api/v1/points/1",
    },
    "points-list": {
        "method": "GET",
        "url": "/api/v1/points",
    },
    "points-filtered-list": {
        "method": "GET",
        "url": "/api/v1/points?project=1",
    },
    "application-tokens-get": {
        "method": "GET",
        "url": "/api/v1/application-tokens/1",
    },
    "application-tokens-delete": {
        "method": "DELETE",
        "url": "/api/v1/application-tokens/1",
    },
    "application-tokens-validate": {
        "method": "POST",
        "url": "/api/v1/application-tokens/validate",
        "body": {
            "application": "a60c3208-5234-11e5-96df-68f72800aadd",
            "auth_code": "21ce08c4-5237-11e5-a8a3-68f72800aadd",
            "state": "random-state"
        }
    },
    "application-tokens-list": {
        "method": "GET",
        "url": "/api/v1/application-tokens",
    },
    "application-tokens-authorize": {
        "method": "POST",
        "url": "/api/v1/application-tokens/authorize",
        "body": {
            "application": "a60c3208-5234-11e5-96df-68f72800aadd",
            "state": "random-state"
        }
    },
    "tasks-custom-attributes-patch": {
        "method": "PATCH",
        "url": "/api/v1/task-custom-attributes/1",
        "body": {
          "name": "Duration"
        }
    },
    "tasks-custom-attributes-create": {
        "method": "POST",
        "url": "/api/v1/task-custom-attributes",
        "body": {
            "name": "Duration",
            "description": "Duration in minutes",
            "order": 8,
            "project": 3
        }
    },
    "tasks-custom-attributes-simple-create": {
        "method": "POST",
        "url": "/api/v1/task-custom-attributes",
        "body": {
            "name": "Duration",
            "project": 3
        }
    },
    "tasks-custom-attributes-get": {
        "method": "GET",
        "url": "/api/v1/task-custom-attributes/1",
    },
    "tasks-custom-attributes-bulk-update-order": {
        "method": "POST",
        "url": "/api/v1/task-custom-attributes/bulk_update_order",
        "body": {
            "project_id": 3,
            "bulk_task_custom_attributes": [[1,10], [2,5]]
        }
    },
    "tasks-custom-attributes-delete": {
        "method": "DELETE",
        "url": "/api/v1/task-custom-attributes/1",
    },
    "tasks-custom-attributes-list": {
        "method": "GET",
        "url": "/api/v1/task-custom-attributes",
    },
    "tasks-custom-attributes-filtered-list": {
        "method": "GET",
        "url": "/api/v1/task-custom-attributes?project=1",
    },
    "locales": {
        "method": "GET",
        "url": "/api/v1/locales",
    },
    "milestones-unwatch": {
        "method": "POST",
        "url": "/api/v1/milestones/1/unwatch",
    },
    "milestones-stats": {
        "method": "GET",
        "url": "/api/v1/milestones/1/stats",
    },
    "milestones-patch": {
        "method": "PATCH",
        "url": "/api/v1/milestones/1",
        "body": {
            "name": "Sprint 2"
        }
    },
    "milestones-create": {
        "method": "POST",
        "url": "/api/v1/milestones",
        "body": {
            "project": 3,
            "name": "Sprint 1",
            "estimated_start": "2014-10-20",
            "estimated_finish": "2014-11-04",
            "disponibility": 30,
            "slug": "sprint-1",
            "order": 1,
            "watchers": []
        }
    },
    "milestones-simple-create": {
        "method": "POST",
        "url": "/api/v1/milestones",
        "body": {
          "project": 3,
          "name": "Sprint 3",
          "estimated_start": "2014-10-20",
          "estimated_finish": "2014-11-04"
        }
    },
    "milestones-get": {
        "method": "GET",
        "url": "/api/v1/milestones/1",
    },
    "milestones-watch": {
        "method": "POST",
        "url": "/api/v1/milestones/1/watch",
    },
    "milestones-delete": {
        "method": "DELETE",
        "url": "/api/v1/milestones/1",
    },
    "milestones-list": {
        "method": "GET",
        "url": "/api/v1/milestones",
    },
    "milestones-filtered-list": {
        "method": "GET",
        "url": "/api/v1/milestones?project=1",
    },
    "milestones-watchers": {
        "method": "GET",
        "url": "/api/v1/milestones/1/watchers",
    },
    "users-stats": {
        "method": "GET",
        "url": "/api/v1/users/1/stats",
    },
    "users-voted": {
        "method": "GET",
        "url": "/api/v1/users/1/voted",
    },
    "users-liked": {
        "method": "GET",
        "url": "/api/v1/users/1/liked?type=userstory&q=test",
    },
    "users-remove-avatar": {
        "method": "POST",
        "url": "/api/v1/users/remove_avatar",
    },
    "users-patch": {
        "method": "PATCH",
        "url": "/api/v1/users/1",
        "body": {
            "username": "patchedusername"
        }
    },
    "users-get": {
        "method": "GET",
        "url": "/api/v1/users/1",
    },
    "users-cancel": {
        "method": "POST",
        "url": "/api/v1/users/cancel",
        "body": {
          "cancel_token": "'${CANCEL_TOKEN}'"
        }
    },
    "users-liked": {
        "method": "GET",
        "url": "/api/v1/users/1/liked",
    },
    "users-filtered-liked": {
        "method": "GET",
        "url": "/api/v1/users/1/liked?q=test",
    },
    "users-contacts": {
        "method": "GET",
        "url": "/api/v1/users/1/contacts",
    },
    "users-delete": {
        "method": "DELETE",
        "url": "/api/v1/users/1",
    },
    "users-chage-password-from-recovery": {
        "method": "POST",
        "url": "/api/v1/users/change_password_from_recovery",
        "body": {
          "token": "'${CHANGE_PASSWORD_TOKEN}'",
          "password": "'${NEW_TOKEN}'"
        }
    },
    "users-change-avatar": {
        "method": "MULTIPART-POST",
        "url": "/api/v1/users/change_avatar",
        "body": {"avatar": "@/tmp/test.png" }
    },
    "users-change-password": {
        "method": "POST",
        "url": "/api/v1/users/change_password",
        "body": {
            "current_password": "'${CURRENT_PASSWORD}'",
            "password": "'${NEW_PASSWORD}'"
        }
    },
    "users-list": {
        "method": "GET",
        "url": "/api/v1/users",
    },
    "users-filtered-list": {
        "method": "GET",
        "url": "/api/v1/users?project=1",
    },
    "users-change-email": {
        "method": "POST",
        "url": "/api/v1/users/change_email",
        "body": {
            "email_token": "'${EMAIL_TOKEN}'"
        }
    },
    "users-watched": {
        "method": "GET",
        "url": "/api/v1/users/1/watched",
    },
    "users-filtered-watched": {
        "method": "GET",
        "url": "/api/v1/users/1/watched?type=project&q=test",
    },
    "users-password-recovery": {
        "method": "POST",
        "url": "/api/v1/users/password_recovery",
        "body": {
            "username": "'${USERNAME_OR_EMAIL}'"
        }
    },
    "users-me": {
        "method": "GET",
        "url": "/api/v1/users/me",
    },
    "user-stories-custom-attributes-values-patch": {
        "method": "PATCH",
        "url": "/api/v1/userstories/custom-attributes-values/1",
        "body": {
            "attributes_values": {"1": "240 min"},
            "version": 2
        }
    },
    "user-stories-custom-attributes-values-get": {
        "method": "GET",
        "url": "/api/v1/userstories/custom-attributes-values/1",
    },
    "applications-get": {
        "method": "GET",
        "url": "/api/v1/applications/a60c3208-5234-11e5-96df-68f72800aadd",
    },
    "applications-token": {
        "method": "GET",
        "url": "/api/v1/applications/a60c3208-5234-11e5-96df-68f72800aadd/token",
    },
    "resolver-milestone": {
        "method": "GET",
        "url": "/api/v1/resolver?project=taiga\&milestone=sprint-0",
    },
    "resolver-user-story": {
        "method": "GET",
        "url": "/api/v1/resolver?project=taiga\&us=1",
    },
    "resolver-wiki-page": {
        "method": "GET",
        "url": "/api/v1/resolver?project=taiga\&wikipage=home",
    },
    "resolver-issue": {
        "method": "GET",
        "url": "/api/v1/resolver?project=taiga\&issue=1485",
    },
    "resolver-project": {
        "method": "GET",
        "url": "/api/v1/resolver?project=taiga",
    },
    "resolver-task": {
        "method": "GET",
        "url": "/api/v1/resolver?project=taiga\&task=915",
    },
    "resolver-ref": {
        "method": "GET",
        "url": "/api/v1/resolver?project=taiga\&ref=915",
    },
    "resolver-multiple": {
        "method": "GET",
        "url": "/api/v1/resolver?project=taiga\&task=915\&us=1\&wikipage=home",
    },
}


class Command(BaseCommand):
    help = 'Generate json files for documentation'

    def _build_curl_cmd(self, host, req):
        data = {
            "method": req['method'],
            "url": req['url'],
            "host": host,
            "body": req.get('body', None),
        }
        if data['method'] == "MULTIPART-POST":
            data['method'] = "POST"

        if data['body'] is not None:
            data['body'] = json.dumps(data['body'])

        template = Template("""curl -X {{method}} \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer ${AUTH_TOKEN}" \\
{% if body %}-d '{{body}}' \\
{% endif %}{{host}}{{url}}
""")
        return template.render(**data)

    def _generate_sample_data(self):
        # raise NotImplementedError
        pass

    def _execute_requests(self, reqs):
        host = "http://localhost:8000"
        for (key, req) in reqs.items():
            cmd_path = os.path.join("output", key + "-cmd.adoc")
            os.makedirs("output", exist_ok=True)
            curl_cmd = self._build_curl_cmd(host, req)
            with open(cmd_path, "w") as fd:
                fd.write(curl_cmd)

            output_path = os.path.join("output", key + "-output.adoc")
            result = subprocess.check_output(curl_cmd, shell=True)
            if result == b'':
                continue
            print(curl_cmd)
            print(result)
            with open(output_path, "w") as fd:
                json.dump(json.loads(result.decode('utf-8')), fd, sort_keys=True, indent=4)

    def handle(self, *args, **options):
        self._generate_sample_data()
        self._execute_requests(reqs)
