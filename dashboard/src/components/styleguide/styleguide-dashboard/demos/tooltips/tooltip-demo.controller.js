(function () {
    'use strict';

    angular.module('app.styleguide')
        .controller('TooltipDemoController', ControllerFunction);

    // ----- ControllerFunction -----
    ControllerFunction.$inject = ['$scope', '$sce'];

    /* @ngInject */
    function ControllerFunction($scope, $sce) {
        var vm = this;

        init();

        function init() {
            $scope.dynamicTooltip = 'Hello, World!';
            $scope.dynamicTooltipText = 'dynamic';
            $scope.htmlTooltip = $sce.trustAsHtml('I\'ve been made <b>bold</b>!');
            $scope.placement = {
                options: [
                    'top',
                    'top-left',
                    'top-right',
                    'bottom',
                    'bottom-left',
                    'bottom-right',
                    'left',
                    'left-top',
                    'left-bottom',
                    'right',
                    'right-top',
                    'right-bottom'
                ],
                selected: 'top'
            };
        }
    }
})();