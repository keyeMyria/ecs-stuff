var gulp = require('gulp');
var watch = require('gulp-watch');

module.exports = function (config) {
    config.log('Importing icon-fonts.js...');

    var $ = config.$;

    var iconSrc = config.sourceDir + 'core/icon-font/icon-src/*.svg';
    var fontName = 'gettalent-icons';

    gulp.task('icon-font', function () {
        gulp
            .src(iconSrc)
            .pipe($.iconfont({
                fontName           : fontName,
                fontHeight         : 150,
                appendUnicode      : false,
                normalize          : true,
                centerHorizontally : true,
                formats            : ['ttf', 'eot', 'woff'],
                autohint           : true,
                timestamp          : Math.round(Date.now() / 1000),
            }))
            .on('glyphs', function (glyphs, options) {
                console.log(glyphs, options);
                gulp
                    .src(config.sourceDir + 'core/icon-font/icon-template.scss')
                    .pipe($.consolidate('lodash', {
                        glyphs: glyphs,
                        fontName: fontName,
                        fontPath: '../fonts/',
                        className: 'icon'
                    }))
                    .pipe($.rename(fontName + '.scss'))
                    .pipe(gulp.dest(config.sourceDir + 'core/icon-font/'));
                gulp
                    .src(config.sourceDir + 'core/icon-font/' + fontName + '.scss')
                    .pipe($.plumber()) // exit gracefully if something fails after this
                    .pipe($.sass({
                        outputStyle: 'expanded'
                    }))
                    .pipe($.rename(fontName + '-gallery.css'))
                    .pipe(gulp.dest(config.sourceDir + 'core/icon-font/'));
                gulp
                    .src(config.sourceDir + 'core/icon-font/icon-gallery-template.html')
                    .pipe($.consolidate('lodash', {
                        glyphs: glyphs,
                        fontName: fontName,
                        fontPath: '../fonts/',
                        targetPath: './',
                        className: 'icon'
                    }))
                    .pipe($.rename(fontName + '.html'))
                    .pipe(gulp.dest(config.sourceDir + 'core/icon-font/'));
            })
            .pipe(gulp.dest(config.sourceDir + 'core/icon-font/'));
    });

    gulp.task('icon-watcher', function () {
        watch(iconSrc, ['icon-font']);
    });
};
