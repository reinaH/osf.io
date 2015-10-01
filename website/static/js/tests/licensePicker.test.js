/*global describe, it, expect, example, before, after, beforeEach, afterEach, mocha, sinon*/
'use strict';
var assert = require('chai').assert;
var utils = require('tests/utils');
var faker = require('faker');

var licenses = require('list-of-licenses');
var $ = require('jquery');
var bootbox = require('bootbox');

var LicensePicker = require('js/licensePicker');

var saveUrl = faker.internet.ip();
var saveMethod = 'POST';
var saveLicenseKey = 'node_license';
var license = licenses.MIT;

describe('LicensePicker', () => {

    before(() => {
        window.contextVars = $.extend({}, window.contextVars || {}, {
            currentUser: {
                isAdmin: true
            }
        });
    });
    var lp;
    beforeEach(() => {
        lp = new LicensePicker(saveUrl, saveMethod, saveLicenseKey, license);
    });

    describe('#selectedLicenseId', () => {
        describe('getter', () => {
            it('returns the id of the current selectedLicense', () => {
                assert.equal(lp.selectedLicenseId(), 'MIT');
                lp.selectedLicense(licenses.GPL3);
                assert.equal(lp.selectedLicenseId(), 'GPL3');
            });
        });
        describe('setter', () => {
            it('updates the current selectedLicense', () => {
                assert.equal(lp.selectedLicenseId(), 'MIT');
                lp.selectedLicenseId('GPL3');
                assert.equal(lp.selectedLicense().id, 'GPL3');
            });

        });
    });
    describe('#togglePreview', () => {
        it('toggles the VM preview state', () => {
            assert.isFalse(lp.previewing());
            lp.togglePreview();
            assert.isTrue(lp.previewing());
        });
    });
    describe('#save', () => {
        var dialogStub;
        var ajaxStub;
        beforeEach(() => {            
            dialogStub = sinon.stub(bootbox, 'dialog');
            ajaxStub = sinon.stub($, 'ajax', function() {
                var ret = $.Deferred();
                ret.resolve();
                return ret.promise();
            });
            sinon.stub(lp, 'disableSave', function() {return false;});
        });
        afterEach(() => {
            bootbox.dialog.restore();
            $.ajax.restore();
            if (lp.disableSave.restore) {
                lp.disableSave.restore();
            }
        });
        it('returns without saving if required fields are missing', () => {
            lp.disableSave.restore();
            lp.save();
            assert.isFalse(dialogStub.called);
            assert.isFalse(ajaxStub.called);
        });
        it('asks confirmation if the user has selected the OTHER license', () => {
            lp.selectedLicenseId('OTHER');
            lp.save();
            assert.calledOnce(dialogStub);
        });
        it('otherwise makes a request based on the value of saveUrl, saveMethod, and saveLicenseKey', (done) => {
            lp.selectedLicenseId('MIT');

            var payload = {};
            payload[saveLicenseKey] = lp.selectedLicense();
            lp.save().always(function() {
                var args = {
                    url: saveUrl,
                    method: saveMethod,
                    contentType: 'application/json',
                    data: JSON.stringify(payload)
                };
                assert.isTrue(ajaxStub.calledWith(args));                             
                done();
            }); 
        });
    });
});
