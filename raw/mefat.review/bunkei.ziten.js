var cacheName = 'bunkei';
var store = new xStore("bunkei:", localStorage);
var typingTimer;
var doneTypingInterval = 2000;
var currentHeading;
var backward;
var forward = [];
var isAndroid = /(android)/i.test(navigator.userAgent);
var isiOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
var isLinux = /linux/i.test(navigator.userAgent);
var isFirefox = /firefox/i.test(navigator.userAgent);
var isChrome = /Chrome/.test(navigator.userAgent) && /Google Inc/.test(navigator.vendor);
var rebuildTOC = true;
var toc;
var dict;
var trans; /* translation */
// var scrolling = false;
var sitvff = "center"; /* scrollIntoView */
var version;
var myID = guid();
var language;
var minchoReady = false;
var gothicReady = false;
var textReady = false;
var timeChecked;

var touch = 'ontouchstart' in document.documentElement
        || navigator.maxTouchPoints > 0
        || navigator.msMaxTouchPoints > 0;

const cacheAvailable = 'caches' in self;

var toFullWidth = str => str.replace(/[!-~]/g, c => String.fromCharCode(c.charCodeAt(0) + 0xFEE0));
var toHalfWidth = str => str.replace(/[！-～]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));

function getUrlVars() {
    var vars = {};
    window.location.search.replace(/[?&]+([^=&]+)=([^&]*)/gi, function(m,key,value) { vars[key] = value; });
    return vars;
}

function getUrlParam(parameter, defaultvalue){
    var urlparameter = defaultvalue;
    if(window.location.href.indexOf(parameter) > -1){
        urlparameter = getUrlVars()[parameter];
        }
    return urlparameter;
}

// https://vhostvn.bot.nu/bunkei.ziten.html?text=test
// getUrlParam("text") => "test"
// getUrlParam("wtf") => undefined

/* Fake GUID */
function guid() {
    return s4() + s4() + '-' + s4() + '-' + s4() + '-' +
        s4() + '-' + s4() + s4() + s4();
}

function s4() {
    return Math.floor((1 + Math.random()) * 0x10000)
        .toString(16)
        .substring(1);
}
/* Fake GUID */

function pickRandomProperty(obj) {
    var result;
    var count = 0;
    for (var prop in obj)
        if (Math.random() < 1/++count)
            result = prop;
    return result;
}

function displayTOC(tocToDisplay) {
    if (rebuildTOC) {
    	rebuildTOC = false;

        var tocA = ""
        jQuery.each(tocToDisplay, function(index, value) {
            tocA += `<a id=${value.id}>${value.keyword}</a>`;
        })
        $('#toc').html("");
        $("#toc").append(tocA);
    }
}

function doneTyping() {
    var filter, sort;
    if ($("#search").val() == "") {
        rebuildTOC = true;
        displayTOC(toc);
        return;
    }
    filter = _.filter(toc, function(value) {
        if (value.keyword.match($("#search").val())) {
            return true;
        } else {
            return false;
        }
    });
    if (filter.length != 0) {
        sort = _.sortBy(filter, function(value) {
            return value.keyword.length
        });
        rebuildTOC = true;
        displayTOC(sort);
        $("#" + _.first(sort).id)[0].scrollIntoView();
        rebuildTOC = true;
    } else {
        $('#toc').html("");
        rebuildTOC = true;
    }
}

function hideRT(rt) {
    rt.css('visibility', 'hidden');
}

function updateMainContent(item) {
    $('#mainContent').html("");

    var newContent = dict[item];
    var pt = /λ.+?μ/g;
    var match;

    while (match = pt.exec(newContent)) {
        var a
        if (match[0].length > 5) {
            a = toHalfWidth( match[0].replace("λ", "").replace("μ", "").replace(/\u3000/g, " ") );
        } else {
            if ( CSS.supports("text-combine-upright", "all") ) {
                a = toHalfWidth( match[0].replace("λ", "<digit>").replace("μ", "</digit>") );
            } else {
                a = match[0].replace("λ", "").replace("μ", "");
            }

        }
        newContent = newContent.replace(match[0], a);
    }

    var m = newContent.match(/【.+?】/g);
    $.each(m, function(index, value) {
        keyword = value.slice(1, -1);
        hasKey = _.find(toc, function(value) {
            return value.keyword == keyword
        })
        if (hasKey) {
            re = new RegExp(value, "g");
            newContent = newContent.replace(re, `<a data-target=${hasKey.id}>${value}</a>`);
        }
    });
    $('#mainContent').append(newContent);
}

function displayNewContent(heading) {
    if (currentHeading && currentHeading == heading) { return }

    $("#mainContent").css("visibility", "hidden");
    $("#spinnerContainer").show();

    if (currentHeading) {
        backward.push(currentHeading);
        if ( backward.length > 99) {
            backward.shift();
        }
        $("#history-backward").data("disabled", 0);
        $('#history-backward').css('color', '#666666');
    }

    currentHeading = heading;

    updateMainContent(currentHeading);

    store.set('currentHeading', currentHeading);
    store.set('history', backward);
    store.set('scroll', 0);
    $(window).scrollLeft(0);
}

async function getData(filename, same) {
    // same: true/false. false will delete file
    var myCache;
    var dataReturn;

    if (cacheAvailable) {
        await caches.open(cacheName).then((cache) => {
            myCache = cache
        });

        if (!same) {
            await myCache.delete(filename);
        }

        await myCache.match(filename)
        .then(
            (resp) => {
                if (resp) {
                    return resp.json()
                } else {
                    return myCache.add(filename)
                    .then(
                        () => {
                            return myCache.match(filename)
                            .then(
                                (resp) => {
                                    return resp.json()
                                }
                            )
                        }
                    )
                }
            }
        )
        .then(
            (data) => {
                dataReturn = data
            }
        );
        return dataReturn;
    } else {
        await $.getJSON(filename, function(data) {
            dataReturn = data
        });
        return dataReturn;
    }
}

function closeSideBar() {
    if ( $("#sideBar").hasClass("open") ) {
        $("#sideBar").removeClass("open");
        $("#pullout").removeClass("open");
        $(`#${currentHeading}`).removeClass('currentTocItem');
    }
}

function dataReady() {
    if ( !(minchoReady && gothicReady && textReady) ) {
        return
    }

    if (isFirefox) {
        sitvff = "start"; /* scrollIntoView */
    }

    if (touch) {
    } else {
        var sheet = document.createElement('style')
        sheet.innerHTML = "ruby:hover rt {visibility: visible;}";
        document.body.appendChild(sheet);
    }

    language = store.get("language", "jp");
    switch(language) {
        case "jp":
            $("#langJP").prop("checked", true);
            break;
        case "vi":
            $("#langVI").prop("checked", true);
            $("#language").html("<span style='font-family:monospace;'>VI</span>");
            break;
    }
    store.set("language", language);

    $('#history-forward').data("disabled", 1);
    $('#history-backward').data("disabled", 1);

    backward = store.get("history", []);
    if (backward.length > 0) {
        $('#history-backward').css('color', '#666666');
        $('#history-backward').data("disabled", 0);
    }

    $("#random").click(() => {
        var ran = pickRandomProperty(dict);
        if (ran == "version") { return }
        displayNewContent(ran);
        closeSideBar();
    });

    $("#history-forward").click(() => {
        if ( $('#history-forward').data("disabled") ) { return }

        displayNewContent(forward.pop());
        closeSideBar();
        if (forward.length == 0) {
            $('#history-forward').css('color', '#ccc');
            $('#history-forward').data("disabled", 1);
        }
    });

    $("#history-backward").click(() => {
        if ( $("#history-backward").data("disabled") ) { return }

        displayNewContent( backward.pop() );
        closeSideBar();
        forward.push( backward.pop() );
        store.set('history', backward);
        if (backward.length == 0) {
            $('#history-backward').css('color', '#ccc');
            $('#history-backward').data("disabled", 1);
        }
        $('#history-forward').css('color', '#666666');
        $('#history-forward').data("disabled", 0);
    });

    $("#permalink").click(() => {
        showModal( `https://mefat.review/bunkei.ziten.html?item=${currentHeading}`, "trans" );
    });

    var urlHeading = getUrlParam("item");
    if (urlHeading) {
        if (dict[urlHeading]) {
            displayNewContent(urlHeading);
        } else {
            alert("Cannot find the grammar point. Please check the link!");
        }

    } else {
        currentHeading = store.get('currentHeading');
        if ( !currentHeading ) {
            ran = pickRandomProperty(dict);
            displayNewContent(ran);
        } else {
            updateMainContent(currentHeading);
            $(window).scrollLeft(store.get('scroll'));
        }
    }

    $("#pullout").click(() => {
        $("#tocFooter").html(`Last updated ${vagueTime.get({to: dict.version * 1000, from: Date.now()})}.<br>Last checked at ${timeChecked}.`);
        if ( !$("#sideBar").hasClass("open") ) {
            $("#search").val("");
            displayTOC(toc);
            $(`#${currentHeading}`).addClass('currentTocItem');
            $(`#${currentHeading}`)[0].scrollIntoView({block: sitvff});
        }
        $("#sideBar").toggleClass("open");
        $("#pullout").toggleClass("open");
    });

    wanakana.bind($("#search").get(0));

    $("#search").on("input", () => {
        clearTimeout(typingTimer);
        typingTimer = setTimeout(doneTyping, doneTypingInterval);
    });

    $("#language").click(function() {
        $("#langBar").toggleClass("openLang");
    });

    $("#langBar input[type='radio']").on('change', function() {
        var selectedValue = $("input[name='rr']:checked").val();
        if (selectedValue && selectedValue == "jp") {
            $("#language").html("<span style='font-family:monospace;'>JP</span>");
            $(".translation").removeClass("translation-on").addClass("translation-off");
        }

        if (selectedValue && selectedValue == "vi") {
            $("#language").html("<span style='font-family:monospace;'>VI</span>");
            $(".translation").removeClass("translation-on").addClass("translation-off");
            $(".vi").removeClass("translation-off").addClass("translation-on");
        }
        store.set("language", selectedValue);
        language = selectedValue;
        $("#langBar").toggleClass("openLang");
    });

    $("#help").click(function() {
        showModal( "<img src='help.gif' style='width:200px;height:349px;'><br><span style='font-size: xx-small;'>Errata, bugs ... write to ho.phuong.nam@gmail.com</span>", "trans" );
    });

    $("#toc").mutationObserver(() => {
        $('#toc a').click(function(e) {
            e.preventDefault();
            heading = $(this).attr('id');
            closeSideBar();
            displayNewContent(heading);
        });
    });

    $("#mainContent").click(function() {
        closeSideBar();
    });

    $("#mainContent").mutationObserver(() => {
        var str = $("div.heading span.keyword").text();
        var m = str.match(/[１２３４５]/);
        if (m) {
            str = str.replace(m, `<sub>${m}</sub>`);
            $("div.heading span.keyword").html(str);
        }

        /*if (isAndroid && isChrome) {
            $(".heading").after("<div id=titleSentinel></div>");
            $("#titleSentinel").on("scrolling", function() {
                if ( $(this).offset().left > $(window).scrollLeft() + document.documentElement.clientWidth) {
                    $("#stickyPanelContainer").css("visibility", "visible");
                } else {
                    $("#stickyPanelContainer").css("visibility", "hidden");
                }
            });
            $("#titleSentinel").trigger("scrolling");
            $(".heading").css("position", "initial");
        }*/

        $("#stickyPanel").text( $(".heading .keyword").text() );

        $("digit").each(function(i, e) {
            var fullWidth = $(e).text();
            var halfWidth = toHalfWidth(fullWidth);
            $(e).text(halfWidth);
        });

        if ( $(".heading .kanji").length > 0 ) {
            $(".heading .keyword").hide();
        }

        $('#mainContent a').click(function(e) {
            e.preventDefault();
            closeSideBar();
            heading = $(this).data('target');
            displayNewContent(heading);
        });

        if (touch) {
            // $('#mainContent ruby').not("#mainContent strong ruby").click(function() {
            $('#mainContent ruby').click(function() {
                rt = $(this).find('rt');
                if (rt.css('visibility') == 'hidden') {
                    rt.css('visibility', 'visible');
                    delayed.delay(hideRT, 5000, rt, rt)
                }
            });
        }

        $(".vi").click(function() {
            showModal( trans[ $(this).data("vi") ].vi, "trans" );
        });

        switch(language) {
            case "jp":
                $(".translation").removeClass("translation-on").addClass("translation-off");
                break;
            case "vi":
                $(".translation").removeClass("translation-on").addClass("translation-off");
                $(".vi").removeClass("translation-off").addClass("translation-on");
                break;
        }

        $("#spinnerContainer").hide();
        $("#mainContent").css("visibility", "visible");
    });

    $("#spinnerContainer").hide();
    $("#spinnerContainer").css("top", "51px");
    $("#spinnerContainer").css("z-index", "2");
    $("#mainContent").css("visibility", "visible");

    /*$(window).scroll(() => {
        scrolling = true;
    });

    setInterval(() => {
        if (scrolling) {
            scrolling = false;
            store.set('scroll', $(window).scrollLeft());

            if (isAndroid && isChrome) {
                $("#titleSentinel").trigger("scrolling");
            }
        }
    }, 100);*/

    setInterval(function() {
        if ( !$("#sideBar").hasClass("open") ) {
            displayTOC(toc);
        }
    }, 1000);

    setInterval(() => {
        $.getScript('bunkei.ziten.version.js', function() {
            timeChecked = new Date().toLocaleString();
            if (version != dict.version) {
                Promise.all([getData('toc.json', false), getData('dict.json', false), getData('trans.json', false)]).then(
                    (values) => {
                        toc   = values[0];
                        dict  = values[1];
                        trans = values[2];
                        updateMainContent(currentHeading);
                        $(window).scrollLeft(store.get('scroll'));
                    }
                );
            }
        });
    }, 300000);

    $.getScript('bunkei.ziten.version.js', function() {
        delayed.delay(function() {
            timeChecked = new Date().toLocaleString();
            if (version != dict.version) {
                Promise.all([getData('toc.json', false), getData('dict.json', false), getData('trans.json', false)]).then(
                    (values) => {
                        toc   = values[0];
                        dict  = values[1];
                        trans = values[2];
                        updateMainContent(currentHeading);
                        $(window).scrollLeft(store.get('scroll'));
                        rebuildTOC = true;
                    }
                );
            }
        }, 1000);
    });
}

$( document ).ready(() => {
    if (isAndroid && isChrome) {
        $("body").css("padding-bottom", "1.5em");

        // fix Android Chrome menu a tag invisible when item is long (needed horizontal scroll)
        $("#mainContent").css("position", "fixed");
        $("#mainContent").css("overflow", "auto");
        $("#mainContent").css("width", "100%");
        $("#mainContent").css("padding-right", "1em");
        $("body").css("padding-right", "unset");
        $("#stickyPanelContainer").css("visibility", "visible");
    }

    Promise.all([getData('toc.json', true), getData('dict.json', true), getData('trans.json', true)]).then(
        (values) => {
            toc   = values[0];
            dict  = values[1];
            trans = values[2];
            textReady = true;
            dataReady();
        }
    );

    if (cacheAvailable) {
        caches.open(cacheName).catch(() => alert('Switch to HTTPS please!'));

        var mincho = isFontAvailable("Yu Mincho");
        var gothic = isFontAvailable("Yu Gothic");

        if ( !mincho ) {
            caches.open(cacheName).then((cache) => {
                cache.match("mincho.json").then(
                    function(resp) {
                        if (resp) { // Font cached
                            getData('mincho.json', true).then(
                                function(value) {
                                    var sheetMincho = document.createElement('style');
                                    sheetMincho.innerHTML = `@font-face{font-family:CustomMincho;src:url(data:font/ttf;base64,${value.mincho})}`;
                                    document.body.appendChild(sheetMincho);
                                    fontLoader = new FontLoader(["CustomMincho"], {
                                        "complete": () => {
                                            minchoReady = true;
                                            dataReady();
                                        }
                                    }, null);
                                    fontLoader.loadFonts();
                                }
                            )
                        } else {
                            getData('mincho.json', true).then(
                                function(value) {
                                    var sheetMincho = document.createElement('style');
                                    sheetMincho.innerHTML = `@font-face{font-family:CustomMincho;src:url(data:font/ttf;base64,${value.mincho})}`;
                                    document.body.appendChild(sheetMincho);
                                }
                            )
                            minchoReady = true;
                            dataReady();
                        }
                    }
                )
            })
        } else {
            minchoReady = true;
            dataReady();
        }

        if ( !gothic ) {
            caches.open(cacheName).then((cache) => {
                cache.match("gothic.json").then(
                    function(resp) {
                        if (resp) { // Font cached
                            getData('gothic.json', true).then(
                                function(value) {
                                    var sheetGothic = document.createElement('style');
                                    sheetGothic.innerHTML = `@font-face{font-family:CustomGothic;src:url(data:font/ttf;base64,${value.gothic})}`;
                                    document.body.appendChild(sheetGothic);
                                    fontLoader = new FontLoader(["CustomGothic"], {
                                        "complete": () => {
                                            gothicReady = true;
                                            dataReady();
                                        }
                                    }, null);
                                    fontLoader.loadFonts();
                                }
                            )
                        } else {
                            getData('gothic.json', true).then(
                                function(value) {
                                    var sheetGothic = document.createElement('style');
                                    sheetGothic.innerHTML = `@font-face{font-family:CustomGothic;src:url(data:font/ttf;base64,${value.gothic})}`;
                                    document.body.appendChild(sheetGothic);
                                }
                            )
                            gothicReady = true;
                            dataReady();
                        }
                    }
                )
            })
        } else {
            gothicReady = true;
            dataReady();
        }

    } else { // cacheAvailable = false
        $("#title").css('color', 'red');
        minchoReady = true;
        gothicReady = true;
        dataReady();
    }

    // Failsafe, after 1'
    delayed.delay(function () {
        if ( !(minchoReady && gothicReady && textReady) ) {
            if (cacheAvailable) {
                caches.open(cacheName).then((cache) => {
                    cache.delete('toc.json');
                    cache.delete('dict.json');
                    cache.delete('trans.json');
                    cache.delete('mincho.json');
                    cache.delete('gothic.json');
                    alert("Something wrong. Please reload!");
                });
            }
        }
    }, 60000);
});
