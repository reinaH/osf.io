'use strict';

var $ = require('jquery');
var bootbox = require('bootbox');
var Raven = require('raven-js');
var ko = require('knockout');

var ProjectSettings = require('js/projectSettings.js');

var $osf = require('js/osfHelpers');
require('css/addonsettings.css');

var ctx = window.contextVars;

// Initialize treebeard grid for notifications
var ProjectNotifications = require('js/notificationsTreebeard.js');
var $notificationsMsg = $('#configureNotificationsMessage');
var notificationsURL = ctx.node.urls.api  + 'subscriptions/';
// Need check because notifications settings don't exist on registration's settings page
if ($('#grid').length) {
    $.ajax({
        url: notificationsURL,
        type: 'GET',
        dataType: 'json'
    }).done(function(response) {
        new ProjectNotifications(response);
    }).fail(function(xhr, status, error) {
        $notificationsMsg.addClass('text-danger');
        $notificationsMsg.text('Could not retrieve notification settings.');
        Raven.captureMessage('Could not GET notification settings.', {
            url: notificationsURL, status: status, error: error
        });
    });
}

//Initialize treebeard grid for wiki
var ProjectWiki = require('js/wikiSettingsTreebeard.js');
var wikiSettingsURL = ctx.node.urls.api  + 'wiki/settings/';
var $wikiMsg = $('#configureWikiMessage');

if ($('#wgrid').length) {
    $.ajax({
        url: wikiSettingsURL,
        type: 'GET',
        dataType: 'json'
    }).done(function(response) {
        new ProjectWiki(response);
    }).fail(function(xhr, status, error) {
        $wikiMsg.addClass('text-danger');
        $wikiMsg.text('Could not retrieve wiki settings.');
        Raven.captureMessage('Could not GET wiki settings.', {
            url: wikiSettingsURL, status: status, error: error
        });
    });
}

$(document).ready(function() {

    // Apply KO bindings for Node Category Settings
    var categories = [];
    var keys = Object.keys(window.contextVars.nodeCategories);
    for (var i = 0; i < keys.length; i++) {
        categories.push({
            label: window.contextVars.nodeCategories[keys[i]],
            value: keys[i]
        });
    }
    var disableCategory = !window.contextVars.node.parentExists;
    // need check because node category doesn't exist for registrations
    if ($('#nodeCategorySettings').length) {
        var categorySettingsVM = new ProjectSettings.NodeCategorySettings(
            window.contextVars.node.category,
            categories,
            window.contextVars.node.urls.update,
            disableCategory
        );
        $osf.applyBindings(categorySettingsVM, $('#nodeCategorySettings')[0]);
    }

    $('#deleteNode').on('click', function() {
        ProjectSettings.getConfirmationCode(ctx.node.nodeType);
    });

    // TODO: Knockout-ify me
    $('#commentSettings').on('submit', function() {
        var $commentMsg = $('#configureCommentingMessage');

        var $this = $(this);
        var commentLevel = $this.find('input[name="commentLevel"]:checked').val();

        $osf.postJSON(
            ctx.node.urls.api + 'settings/comments/',
            {commentLevel: commentLevel}
        ).done(function() {
            $commentMsg.text('Successfully updated settings.');
            $commentMsg.addClass('text-success');
            if($osf.isSafari()){
                //Safari can't update jquery style change before reloading. So delay is applied here
                setTimeout(function(){window.location.reload();}, 100);
            } else {
                window.location.reload();
            }

        }).fail(function() {
            bootbox.alert({
                message: 'Could not set commenting configuration. Please try again.',
                buttons:{
                    ok:{
                        label:'Close',
                        className:'btn-default'
                    }
                }
            });
        });

        return false;

    });

    var checkedOnLoad = $('#selectAddonsForm input:checked');
    var uncheckedOnLoad = $('#selectAddonsForm input:not(:checked)');

    // Set up submission for addon selection form
    $('#selectAddonsForm').on('submit', function() {

        var formData = {};
        $('#selectAddonsForm').find('input').each(function(idx, elm) {
            var $elm = $(elm);
            formData[$elm.attr('name')] = $elm.is(':checked');
        });

        var unchecked = checkedOnLoad.filter('#selectAddonsForm input:not(:checked)');
        var checked = uncheckedOnLoad.filter('#selectAddonsForm input:checked');
        var msgElm = $(this).find('.addon-settings-message');
        
        var submit = function() {
            var request = $osf.postJSON(ctx.node.urls.api + 'settings/addons/', formData);
            return request;
        };

        function successMessage() {
            msgElm.text('Settings updated');
            setTimeout(
                function() {
                    msgElm.text('');
                },
                5000
            );
        }
        function successfulAddonUpdate() {
            successMessage();
            checkedOnLoad = $('#selectAddonsForm input:checked');
            uncheckedOnLoad = $('#selectAddonsForm input:not(:checked)');
            if($osf.isSafari()) {
                        //Safari can't update jquery style change before reloading. So delay is applied here
                        setTimeout(function(){window.location.reload();}, 100);
            } else {
                        window.location.reload();
            }
        }
        function failedAddonUpdate() {
            var msg = 'Sorry, we had trouble saving your settings. If this persists please contact <a href="mailto: support@osf.io">support@osf.io</a>';
            bootbox.alert({
                title: 'Request failed',
                message: msg,
                buttons: {
                    ok: {
                        label: 'Close',
                        className: 'btn-default'
                    }
                }
            });
        }
        // some addons disabled (unchecked warning adopted from profile-settings-addons-page.js)
        if(unchecked.length > 0) {
            var uncheckedText = $.map(unchecked, function(el){
                return ['<li>', $(el).closest('label').text().trim(), '</li>'].join('');
            }).join('');
            uncheckedText = ['<ul>', uncheckedText, '</ul>'].join('');
            bootbox.confirm({
                title: 'Are you sure you want to remove the add-ons you have deselected? ',
                message: uncheckedText,
                callback: function(result) {
                    if (result) {
                        var request = submit();
                        request.done(successfulAddonUpdate);
                        request.fail(failedAddonUpdate);
                    } else{
                        unchecked.each(function(i, el){ $(el).prop('checked', true); });
                    }
                },
                buttons: {
                    confirm: {
                        label: 'Remove',
                        className: 'btn-danger'
                    }
                }
            });
        }
        //no addons disabled but some addons enabled
        else if(checked.length>0) {
            var request = submit();
            request.done(successfulAddonUpdate);
            request.fail(failedAddonUpdate);
        }
        // no changes to the state of the addons
        else {
            successMessage();
        }

        return false;

    });

    /* Before closing the page, Check whether the newly checked addon are updated or not */
    $(window).on('beforeunload',function() {
      //new checked items but not updated
      var checked = uncheckedOnLoad.filter('#selectAddonsForm input:checked');
      //new unchecked items but not updated
      var unchecked = checkedOnLoad.filter('#selectAddonsForm input:not(:checked)');

      if(unchecked.length > 0 || checked.length > 0) {
        return 'The changes on addon setting are not submitted!';
      }
    });

    // Show capabilities modal on selecting an addon; unselect if user
    // rejects terms
    $('.addon-select').on('change', function() {
        var that = this,
            $that = $(that);
        if ($that.is(':checked')) {
            var name = $that.attr('name');
            var capabilities = $('#capabilities-' + name).html();
            if (capabilities) {
                bootbox.confirm({
                    message: capabilities,
                    callback: function(result) {
                        if (!result) {
                            $(that).attr('checked', false);
                        }
                    },
                    buttons:{
                        confirm:{
                            label:'Confirm'
                        }
                    }
               });
            }
        }
    });

});


